"""
Account self-service routes —— 数据主体权利入口。

对应法定义务：
  * GDPR Art.15 查阅权 / Art.20 可携带权 → ``GET /v1/account/export``
  * GDPR Art.17 删除权（被遗忘权）
  * PIPL 第 45 条（查阅、复制）／第 47 条（删除）
  海内外同一套实现：合规不会因为部署区域而变松。

设计要点：
  * 一律以登录态 ``g.user_id`` 为准，**不接受**任何指定他人 user_id 的参数；
  * 导出沿用 ``DatabaseManager.export_user_data``（与 delete_user 共享行集合，
    并剔除凭据列）；
  * 删除复用 ``DatabaseManager.delete_user`` —— 它按外键反向拓扑序清干净
    （含孙表与无外键表），并在存在已付款订单时抛 ``PaidOrderBlockedError``，
    本层把该异常翻译成 409 + 人工处理指引，绝不静默删掉资金相关记录；
  * 删除写审计轨迹（audit_logs 无外键、默认不被 delete_user 清，正好留痕）；
  * 删除后原 JWT 立即失效 —— ``require_auth`` 每次都会回库查人，
    用户行没了自然 401，无需额外的吊销名单。
"""
from __future__ import annotations

import logging

from flask import Blueprint, current_app, g, jsonify, request

from src.api.auth.decorators import require_auth
from src.compliance.audit import get_audit_logger
from src.db.manager import PaidOrderBlockedError

logger = logging.getLogger("looma.account")

account_bp = Blueprint("account", __name__)

# 注销必须回传的字面量。目的：一个 DELETE 必须"带着意图"来，
# 避免误触、误重放或被一个 <img src> 式请求打中。
DELETE_CONFIRMATION = "DELETE"

# 导出体积上限（单表行数）。DSAR 主张"完整"，但一次把千万行聊天记录塞进
# 单个响应会把 worker 拖死；超出部分在 truncated 里点名，用户可据此进一步索取。
EXPORT_MAX_ROWS_PER_TABLE = 10000


def _db():
    return current_app._db


@account_bp.route("/account/export", methods=["GET"])
@require_auth
def export_my_data():
    """导出当前账号的全部个人数据（机器可读 JSON）。"""
    uid = getattr(g, "user_id", None)
    if not uid:
        return jsonify(error="unauthorized", message="请先登录"), 401

    include_audit = (request.args.get("include_audit") or "").lower() in ("1", "true", "yes")

    try:
        payload = _db().export_user_data(
            uid,
            include_audit=include_audit,
            max_rows_per_table=EXPORT_MAX_ROWS_PER_TABLE,
        )
    except Exception as exc:  # noqa: BLE001 — 导出失败必须显式回报，不能假装成功
        logger.exception("export_user_data failed for %s", uid)
        return jsonify(error="export_failed", message=str(exc)), 500

    get_audit_logger().log_from_request(
        actor=uid,
        action="account_export",
        resource_type="user",
        resource_id=uid,
        metadata={"tables": len(payload["tables"]), "include_audit": include_audit},
    )
    return jsonify(payload), 200


@account_bp.route("/account", methods=["DELETE"])
@require_auth
def delete_my_account():
    """注销当前账号（被遗忘权）。不可撤销，需请求体显式确认。"""
    uid = getattr(g, "user_id", None)
    if not uid:
        return jsonify(error="unauthorized", message="请先登录"), 401

    body = request.get_json(silent=True) or {}
    if (body.get("confirm") or "").strip() != DELETE_CONFIRMATION:
        return jsonify(
            error="confirmation_required",
            message=(
                "注销不可撤销。请在请求体回传 "
                '{"confirm": "%s"} 以确认。' % DELETE_CONFIRMATION
            ),
        ), 400

    try:
        result = _db().delete_user(uid)
    except PaidOrderBlockedError as exc:
        # 资金安全护栏：有真实支付流水的账号不能自助注销
        return jsonify(
            error="paid_orders_exist",
            message="账号存在已支付订单，无法自助注销。请先联系客服处理退款或订阅取消。",
            orders=[o.get("out_trade_no") for o in exc.orders],
        ), 409
    except Exception as exc:  # noqa: BLE001 — 删除失败必须让用户知道，而不是静默半删
        logger.exception("delete_user failed for %s", uid)
        return jsonify(error="delete_failed", message=str(exc)), 500

    # 审计轨迹在删除之后写：audit_logs 不持有外键、且默认不被 delete_user 清理，
    # 恰好留下"谁在什么时候注销了自己"的证据。
    get_audit_logger().log_from_request(
        actor=uid,
        action="account_delete",
        resource_type="user",
        resource_id=uid,
        metadata={"deleted": result.get("deleted", {})},
    )
    logger.info(
        "user %s self-deleted account (%d table(s) touched)",
        uid, len(result.get("deleted", {})),
    )
    return jsonify(
        deleted=True,
        user_id=uid,
        tables=result.get("deleted", {}),
    ), 200

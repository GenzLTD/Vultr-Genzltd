"""
Membership routes blueprint — /v1/membership/*

海外独立站（诗词门户 / PlanetX 海外版）虚拟会员 SaaS 订阅。
复用 payment 引擎（Stripe + Stripe Tax），价格见 payment.v1.json(US)。
协议权威 = contracts/gfcc（GenzLTD/gfcc）。

  GET  /v1/membership/plans         - 公开：列出三档套餐 + 税务/账单主体
  POST /v1/membership/subscribe     - 认证：创建 Stripe 订阅 Checkout
  POST /v1/membership/portal        - 认证：创建 Stripe Billing Portal 会话（自助取消/换卡/发票）
  GET  /v1/membership/status        - 认证：当前会员订阅状态
  POST /v1/membership/webhook/stripe- Stripe webhook（无鉴权，验签）
"""
from urllib.parse import urlparse

from flask import Blueprint, jsonify, g, request, current_app

from src.api.auth.decorators import require_auth
from src.services.membership.service import MembershipService

membership_bp = Blueprint("membership", __name__)
_service = MembershipService()


def _resolve_return_url(req, config, candidate: str) -> tuple[str, bool]:
    """把回跳地址收敛到可信 host，避免把用户从 Stripe 重定向到站外（开放重定向）。

    返回 ``(url, rejected)``：

      * 没有候选（既没传 ``return_url`` 也没有 ``Origin``）→ ``("", False)``，
        交给 Stripe 用它自己的默认回跳；
      * 有候选但不合法 → ``("", True)``，明确拒绝 —— 绝不把用户送去站外。

    可信 host = 当前请求的 host ∪ ``MEMBERSHIP_PORTAL_RETURN_HOSTS``（逗号分隔）。
    海外站前端与 API 不同域名时，把前端域名写进该配置即可。
    """
    allow = {
        h.strip().lower()
        for h in str(config.get("MEMBERSHIP_PORTAL_RETURN_HOSTS", "") or "").split(",")
        if h.strip()
    }
    url = (candidate or "").strip() or (req.headers.get("Origin") or "").strip()
    if not url:
        return "", False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "", True
    if parsed.netloc.lower() not in ({req.host.lower()} | allow):
        return "", True
    return url, False


@membership_bp.route("/membership/plans", methods=["GET"])
def list_plans():
    """List overseas membership plans (region-aware via payment.v1.json US)."""
    payload = _service.list_plans(current_app.config)
    return jsonify(**payload)


@membership_bp.route("/membership/subscribe", methods=["POST"])
@require_auth
def subscribe():
    """Create a Stripe Checkout Session for an overseas membership subscription."""
    data = request.get_json(silent=True) or {}
    tier = data.get("tier")
    success_url = data.get("success_url", "")
    cancel_url = data.get("cancel_url", "")
    origin = request.headers.get("Origin", "") or request.host_url.rstrip("/")

    resp, code = _service.subscribe(
        db=current_app._db,
        config=current_app.config,
        user_id=g.user_id,
        tier=tier,
        success_url=success_url,
        cancel_url=cancel_url,
        origin=origin,
    )
    return jsonify(resp), code


@membership_bp.route("/membership/status", methods=["GET"])
@require_auth
def status():
    """Get current user's membership subscription status."""
    payload = _service.get_status(current_app._db, g.user_id)
    return jsonify(**payload)


@membership_bp.route("/membership/portal", methods=["POST"])
@require_auth
def billing_portal():
    """Create a Stripe Billing Portal session — self-service cancel / card / invoices."""
    data = request.get_json(silent=True) or {}
    return_url, rejected = _resolve_return_url(
        request, current_app.config, data.get("return_url", "")
    )
    if rejected:
        return (
            jsonify(
                error="invalid_return_url",
                message=(
                    "return_url 必须与当前站点同源，或位于 "
                    "MEMBERSHIP_PORTAL_RETURN_HOSTS 白名单内。"
                ),
            ),
            400,
        )

    resp, code = _service.create_billing_portal(
        db=current_app._db,
        config=current_app.config,
        user_id=g.user_id,
        return_url=return_url,
    )
    return jsonify(resp), code


@membership_bp.route("/membership/webhook/stripe", methods=["POST"])
def stripe_webhook():
    """Stripe membership webhook receiver.

    Verifies signature, parses event, settles payment.
    Does NOT require auth — called by Stripe servers.
    """
    payload = request.get_data()
    headers = dict(request.headers)

    resp, code = _service.handle_stripe_webhook(
        db=current_app._db,
        config=current_app.config,
        payload=payload,
        headers=headers,
    )
    return jsonify(resp), code

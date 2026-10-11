"""
Membership routes blueprint — /v1/membership/*

海外独立站（诗词门户 / PlanetX 海外版）虚拟会员 SaaS 订阅。
复用 payment 引擎（Stripe + Stripe Tax），价格见 payment.v1.json(US)。
协议权威 = contracts/gfcc（GenzLTD/gfcc）。

  GET  /v1/membership/plans         - 公开：列出三档套餐 + 税务/账单主体
  POST /v1/membership/subscribe     - 认证：创建 Stripe 订阅 Checkout
  GET  /v1/membership/status        - 认证：当前会员订阅状态
  POST /v1/membership/webhook/stripe- Stripe webhook（无鉴权，验签）
"""
from flask import Blueprint, jsonify, g, request, current_app

from src.api.auth.decorators import require_auth
from src.services.membership.service import MembershipService

membership_bp = Blueprint("membership", __name__)
_service = MembershipService()


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

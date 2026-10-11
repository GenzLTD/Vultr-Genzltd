"""海外会员产品层 —— 诗词门户 / PlanetX 海外版虚拟会员 SaaS 订阅。

薄产品层：复用 payment 引擎（Stripe + Stripe Tax），不重复报价。
价格单一真相源 = backend/contracts/payment.v1.json（US 区，YeDall 主体）。
本协议只声明权益(entitlements)与税务(tax)，见 backend/contracts/membership.v1.json。
"""

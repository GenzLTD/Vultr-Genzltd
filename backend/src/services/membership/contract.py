"""会员产品契约加载 —— 权益与税务的单一真相源（价格见 payment.v1.json）。

协议权威 = contracts/gfcc（GenzLTD/gfcc）。
价格不在此重复声明，直接引用 payment.v1.json 的 US 区。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "membership.v1.json"


@lru_cache(maxsize=1)
def _load_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def get_contract() -> dict[str, Any]:
    return _load_contract()


def get_tax_config() -> dict[str, Any]:
    return _load_contract().get("tax", {})


def get_entitlements() -> dict[str, Any]:
    return _load_contract().get("entitlements", {})


def get_entitlement(tier: str) -> dict[str, Any] | None:
    return get_entitlements().get(tier)

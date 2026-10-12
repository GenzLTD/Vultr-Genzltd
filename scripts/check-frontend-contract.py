#!/usr/bin/env python3
"""前端 bundle <-> 后端路由 契约门禁（部署前）。

判定规则（只有一种情况判失败）：
    前端 bundle 里实际调用的 /v1/* 路径，在**即将发布的后端** url_map 里
    找不到对应规则 -> fail。

后端多出来、前端没用到的路径属于正常增量（新增能力前端还没接），
只报告，不算失败。

路径匹配说明（避免假阴性）：
    前端写的是基址（如 "/v1/resume"），后端注册的是 "/v1/resume/<resume_id>"。
    二者段数不同但语义相同 —— 前端调用时会拼上 id。因此当后端规则**多出来的
    段全部是参数段**时，视为命中。

用法：
    python scripts/check-frontend-contract.py \
        --endpoints-file /tmp/backend-endpoints.json \
        --site https://tspace.genz.ltd \
        --site https://app.genz.ltd
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from typing import Iterable, Sequence

DEFAULT_SITES = [
    "https://tspace.genz.ltd",
    "https://app.genz.ltd",
]

SCRIPT_SRC_RE = re.compile(r"""<script[^>]+src=["']([^"']+\.js)["']""", re.I)
# 端点字面量："/v1/xxx"、'/v1/xxx'、`/v1/xxx`，允许 ${id} / {id} / <id> 形式的参数段
ENDPOINT_RE = re.compile(
    r"""["'`](/v1/[A-Za-z0-9_\-/${}<>.]+)["'`]"""
)
PARAM_SEG_RE = re.compile(r"^(<[^>]+>|\{[^}]*\}|\$\{[^}]*\}|\d+)$")

UA = "Vultr-Genzltd-contract-gate/1.0"


def fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def normalize(path: str) -> list[str]:
    """把路径切成段，参数段统一成 '*'。"""
    segs: list[str] = []
    for seg in path.split("/"):
        if seg == "":
            continue
        segs.append("*" if PARAM_SEG_RE.match(seg) else seg.lower())
    return segs


def rule_to_segs(rule: str) -> list[str]:
    return normalize(rule)


def matches(fe: Sequence[str], be: Sequence[str]) -> bool:
    """前端路径是否命中后端规则（允许后端多出若干参数段）。"""
    if len(fe) > len(be):
        return False
    for i, seg in enumerate(fe):
        if be[i] == "*":
            continue
        if seg == "*" or seg == be[i]:
            continue
        return False
    # 后端多出来的段必须全是参数段
    return all(s == "*" for s in be[len(fe):])


def extract_endpoints(js: str) -> set[str]:
    found: set[str] = set()
    for raw in ENDPOINT_RE.findall(js):
        found.add(raw)
    return found


def collect_site(site: str) -> tuple[list[str], list[str]]:
    """返回 (bundle_urls, endpoints)。"""
    html = fetch(site.rstrip("/") + "/")
    srcs = [s for s in SCRIPT_SRC_RE.findall(html) if "registerSW" not in s]
    bundles: list[str] = []
    endpoints: set[str] = set()
    for src in srcs:
        url = src if src.startswith("http") else site.rstrip("/") + src
        try:
            bundles.append(url)
            endpoints |= extract_endpoints(fetch(url))
        except Exception as exc:  # noqa: BLE001
            print(f"::warning title=无法读取 bundle {url}::{exc}")
    return bundles, sorted(endpoints)


def load_backend_rules(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    rules = data.get("rules") or []
    out: list[str] = []
    for item in rules:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict) and item.get("rule"):
            out.append(item["rule"])
    if not out:
        raise SystemExit(f"::error::{path} 里没有解析到任何后端路由规则")
    return out


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--endpoints-file", required=True,
                    help="dump-backend-endpoints.py 产出的 JSON")
    ap.add_argument("--site", action="append", default=None,
                    help="要校验的前端站点，可重复；默认 tspace + app")
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args(list(argv) if argv is not None else None)

    sites = args.site or DEFAULT_SITES
    rules = load_backend_rules(args.endpoints_file)
    rule_segs = [(r, rule_to_segs(r)) for r in rules]

    used_by_frontend: set[str] = set()
    missing: list[tuple[str, str]] = []
    unreachable: list[str] = []

    for site in sites:
        print(f"\n=== {site} ===")
        try:
            bundles, endpoints = collect_site(site)
        except Exception as exc:  # noqa: BLE001
            print(f"::warning title=站点不可达 {site}::{exc}（本次未校验该站）")
            unreachable.append(site)
            continue

        print(f"bundle: {len(bundles)} 个, 提取 /v1/* 端点 {len(endpoints)} 条")
        if not endpoints:
            print(f"::warning title={site}::未从 bundle 中提取到任何 /v1/* 端点，"
                  f"请确认提取正则是否仍适配产物格式")
        for ep in endpoints:
            used_by_frontend.add(ep)
            segs = normalize(ep)
            if not any(matches(segs, be) for _, be in rule_segs):
                missing.append((site, ep))
                print(f"::error title=前端调用了后端没有的接口::{site} -> {ep}")

    # 后端有、前端没用：只报告
    unused: list[str] = []
    seen_unused: set[str] = set()
    for rule, segs in rule_segs:
        if not rule.startswith("/v1/") or rule in seen_unused:
            continue
        if not any(matches(normalize(ep), segs) for ep in used_by_frontend):
            seen_unused.add(rule)
            unused.append(rule)

    print("\n=== 汇总 ===")
    print(f"后端路由规则: {len(rules)}")
    print(f"前端调用端点: {len(used_by_frontend)}（去重后）")
    print(f"后端新增未接入: {len(unused)}（正常增量，不计失败）")
    for rule in unused[:20]:
        print(f"  - {rule}")
    if len(unused) > 20:
        print(f"  ... 其余 {len(unused) - 20} 条省略")

    if missing:
        print(f"\n::error::契约门禁失败：{len(missing)} 个前端调用的端点在即将发布的后端中不存在")
        for site, ep in missing:
            print(f"  - {site} {ep}")
        return 1

    if unreachable:
        print(f"\n注意：{len(unreachable)} 个站点不可达，未纳入本次校验：{', '.join(unreachable)}")
    print("\n契约门禁通过：前端调用的所有 /v1/* 在即将发布的后端中都存在")
    return 0


if __name__ == "__main__":
    sys.exit(main())

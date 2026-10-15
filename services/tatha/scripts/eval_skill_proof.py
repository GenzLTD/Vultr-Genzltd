#!/usr/bin/env python3
"""Phase 1 验收对照：同一简历「无证明 vs 有证明」→ JobMatchScore 不降 + 技能命中率上升。

流程（全走 HTTP，依赖 Tatha :8010）：
  A. 无证据：POST /v1/jobs/match（带 user_id_hash，store 无证据 → 不增强）
  I. 摄入：  POST /v1/skills/ingest（一条 skill-proof；配置 SIGNAL_BRIDGE_SECRET 则 HMAC 验签）
  B. 有证据：POST /v1/jobs/match（带 user_id_hash → 注入「已验证技能」块）

判据：
  桥接（证据注入成功）：ingest status in {stored, duplicate} 且 B 阶段 verified_skills 非空
  蒸馏（LLM 感知证据）：对齐同职位，B.skills_overlap > A.skills_overlap（技能命中率上升）
                        且 B.overall >= A.overall - tolerance（匹配度不降）
  LLM 不可用：任一阶段所有 overall=0 且 summary 含「打分失败」→ SKIP（不判 PASS/FAIL）

退出码：0=PASS  1=FAIL（区分桥接/蒸馏失败）  2=SKIP
用法：uv run python scripts/eval_skill_proof.py [--base-url http://127.0.0.1:8010]
"""
from __future__ import annotations

import argparse
import hashlib
import hmac as _hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

DEFAULT_BASE_URL = "http://127.0.0.1:8010"
# 固定简历：Python 后端，故意不写 PyTorch / RAG，留给证据补强。
DEFAULT_RESUME = """张三
Python 后端工程师，5 年经验。
熟悉 Python、FastAPI、PostgreSQL、Redis，负责过高并发 API 服务与微服务架构。
了解基础的 LLM 应用开发与向量检索。
"""


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _sign(secret: str, body: bytes) -> str:
    return _hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _post(url: str, payload: dict, headers: dict) -> tuple[int, dict]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    hdrs = {"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"}
    hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, {"error": raw or exc.reason}
    except Exception as exc:
        return 0, {"error": str(exc)}


def _match(base: str, token: str, resume: str, uid: str | None, top_n: int, source: str) -> dict:
    p = {"resume_text": resume, "top_n": top_n, "source": source}
    if uid:
        p["user_id_hash"] = uid
    st, data = _post(base + "/v1/jobs/match", p, {"Authorization": f"Bearer {token}"})
    if st != 200:
        data["_status"] = st
    return data


def _ingest(base: str, secret: str | None, uid: str, nonce: str) -> dict:
    ev = [
        {"skill": "PyTorch", "source": "Guibu 微课：PyTorch 深度学习实战",
         "excerpt": "完成 12 节微课：张量、自动微分、模型训练与 CNN 推理", "learned_at": _iso()},
        {"skill": "RAG", "source": "Guibu 微课：RAG 检索增强生成",
         "excerpt": "完成 RAG 全链路：文档切分、向量检索、prompt 拼接与评估", "learned_at": _iso()},
    ]
    envelope = {"signal_type": "skill_proof", "user_id_hash": uid, "nonce": nonce, "payload": {
        "schema_version": "skill-proof.v1", "user_id": uid, "skill_tags": ["PyTorch", "RAG"],
        "level": "intermediate", "evidence": ev, "total_micro_lessons": len(ev),
        "proofs": [], "generated_at": _iso()}}
    hdrs = {}
    if secret:
        body = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
        hdrs["X-Signature"] = _sign(secret, body)
    st, data = _post(base + "/v1/skills/ingest", envelope, hdrs)
    if st != 200:
        data["_status"] = st
    return data


def _scores(r: dict) -> list[dict]:
    out = []
    for m in r.get("matches") or []:
        job, sc = m.get("job") or {}, m.get("score") or {}
        out.append({"title": job.get("title") or "?", "overall": int(sc.get("overall") or 0),
                    "skills_overlap": int(sc.get("skills_overlap") or 0), "summary": sc.get("summary") or ""})
    return out


def _llm_down(scores: list[dict]) -> bool:
    return (not scores) or all(s["overall"] == 0 and "打分失败" in s["summary"] for s in scores)


def _fmt_verified(vs) -> str:
    if not vs:
        return "(无 — 未注入增强块)"
    lines = ["## 已验证技能（Guibu 微课学习证据，非自述）"]
    for it in vs:
        evs = it.get("evidence") or []
        refs = [f"{e.get('source') or '?'}「{(e.get('excerpt') or '').strip()[:60]}」" for e in evs[:3]]
        lines.append(f"- {it.get('skill') or '?'} — 证据 {len(evs)} 条：{'；'.join(refs)}")
    return "\n".join(lines)


def _align(a: list[dict], b: list[dict]):
    by = {s["title"]: s for s in b}
    pairs = [(s["title"], s, by[s["title"]]) for s in a if s["title"] in by]
    if not pairs and a and b:
        pairs = [(f"{a[0]['title']} / {b[0]['title']}", a[0], b[0])]
    n = len(pairs) or 1
    return pairs, {
        "d_skills": round(sum(p[2]["skills_overlap"] - p[1]["skills_overlap"] for p in pairs) / n, 2),
        "d_overall": round(sum(p[2]["overall"] - p[1]["overall"] for p in pairs) / n, 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("TATHA_SIGNAL_INGEST_URL", DEFAULT_BASE_URL))
    ap.add_argument("--token", default=None, help="Bearer token；缺省随机（stub 模式 free 档）")
    ap.add_argument("--user-email", default=None, help="固定邮箱；缺省时间戳生成唯一 hash，保证 A 无历史证据")
    ap.add_argument("--tolerance", type=float, default=0.0, help="overall 允许下降容差，默认 0=严格不降")
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--source", default="mock")
    ap.add_argument("--resume-file", default=None)
    args = ap.parse_args()

    secret = os.environ.get("SIGNAL_BRIDGE_SECRET") or None
    base = args.base_url.rstrip("/")
    resume = DEFAULT_RESUME
    if args.resume_file:
        resume = open(args.resume_file, encoding="utf-8").read()
    if not resume.strip():
        print("简历为空"); return 2

    email = args.user_email or f"eval-{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
    uid = _sha(email)
    token = args.token or f"eval-{uuid.uuid4().hex}"

    print("=" * 70)
    print("Phase 1 验收对照：无证明 vs 有证明")
    print("=" * 70)
    print(f"base_url={base}\nuser_email={email}\nuser_id_hash={uid}\ntoken={token}")
    print(f"HMAC={'已配置' if secret else '未配置(dev免签)'}  tolerance={args.tolerance}  source={args.source}")

    def dump(tag, scores):
        print(f"[{tag}] total_evaluated 返回 {len(scores)} 条:")
        for s in scores:
            print(f"    {s['title']:<24} overall={s['overall']:>3}  skills_overlap={s['skills_overlap']:>2}")

    print("\n[A] 无证据匹配...")
    ra = _match(base, token, resume, uid, args.top_n, args.source)
    if ra.get("_status") or ra.get("error"):
        print(f"[A] 失败: HTTP {ra.get('_status')} {ra.get('error') or ra}"); return 2
    sa = _scores(ra)
    dump("A", sa)
    if _llm_down(sa):
        print("\n[A] 所有打分为 0 且含「打分失败」→ LLM 不可用。SKIP，不判 PASS/FAIL。")
        print("请检查 .env 的 DEEPSEEK_API_KEY / TATHA_DEFAULT_MODEL。")
        return 2

    print("\n[I] 摄入 skill-proof (PyTorch, RAG)...")
    ri = _ingest(base, secret, uid, uuid.uuid4().hex)
    if ri.get("_status"):
        print(f"[I] 失败: HTTP {ri.get('_status')} {ri}")
        if ri.get("_status") == 401:
            print("    401 验签失败：确认 SIGNAL_BRIDGE_SECRET 与 Tatha 一致。")
        return 2
    print(f"[I] status={ri.get('status')} verified={ri.get('verified')} id={ri.get('evidence_id')} "
          f"count={ri.get('evidence_count')} tags={ri.get('skill_tags')}")

    print("\n[B] 有证据匹配...")
    rb = _match(base, token, resume, uid, args.top_n, args.source)
    if rb.get("_status") or rb.get("error"):
        print(f"[B] 失败: HTTP {rb.get('_status')} {rb.get('error') or rb}")
        if rb.get("_status") == 429:
            print("    429 配额用尽（free 档每日 3 次 job_match）：重启服务或换 --token。")
        return 2
    sb = _scores(rb)
    dump("B", sb)
    vs = rb.get("verified_skills")
    if _llm_down(sb):
        print("\n[B] 打分为 0 → LLM 不可用。SKIP。")
        return 2

    bridge_ok = ri.get("status") in ("stored", "duplicate") and bool(vs)
    pairs, agg = _align(sa, sb)
    d_skills, d_overall = agg["d_skills"], agg["d_overall"]
    distill_skills_ok = d_skills > 0
    distill_overall_ok = d_overall >= -args.tolerance

    print("\n" + "=" * 70)
    print("[桥接] 注入块预览")
    print("=" * 70)
    print(_fmt_verified(vs))
    print(f"→ 桥接{'成功' if bridge_ok else '失败'}（ingest={ri.get('status')}, verified_skills={'非空' if vs else '空'}）")

    print("\n" + "=" * 70)
    print("[对照] 同职位对齐（A→B 差值）")
    print("=" * 70)
    for title, x, y in pairs:
        print(f"    {title:<30} skills {x['skills_overlap']:>2}→{y['skills_overlap']:>2} "
              f"({y['skills_overlap']-x['skills_overlap']:+d})  overall {x['overall']:>3}→{y['overall']:>3} "
              f"({y['overall']-x['overall']:+d})")
    print(f"    平均 Δskills_overlap={d_skills:+}  Δoverall={d_overall:+}")

    print("\n" + "=" * 70)
    if not bridge_ok:
        print("结果：FAIL — 桥接失败（证据未注入简历，检查 ingest / enhance 链路）")
        return 1
    if not distill_skills_ok and not distill_overall_ok:
        print("结果：FAIL — 蒸馏失败（证据已注入，但 LLM 未体现技能命中率上升，且匹配度下降）")
        return 1
    if not distill_skills_ok:
        print("结果：FAIL — 蒸馏失败（技能命中率 skills_overlap 未上升，Δ=%.2f）" % d_skills)
        return 1
    if not distill_overall_ok:
        print(f"结果：FAIL — 蒸馏失败（匹配度下降 Δoverall={d_overall:+}，超容差 {args.tolerance}）")
        return 1
    print(f"结果：PASS — 技能命中率上升（Δskills_overlap={d_skills:+}）且匹配度不降（Δoverall={d_overall:+}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

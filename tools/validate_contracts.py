#!/usr/bin/env python3
"""校验 contracts/gfcc：可解析、同家族 version 一致、仓内 $ref 可解析。

两族互不影响：
  l0     — 除 signal.* 外，当前线见 SOURCE.json（钉 1.3.0）
  signal — signal.envelope.v1.json + signals/*.json（钉 1.0.0）

只认同仓内文件引用，不拉 http(s) $schema。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

DEFAULT_CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts" / "gfcc"


def walk_refs(obj: Any) -> Iterable[str]:
    if isinstance(obj, dict):
        ref = obj.get("$ref")
        if isinstance(ref, str):
            yield ref
        for value in obj.values():
            yield from walk_refs(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk_refs(item)


def unescape_pointer_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def resolve_pointer(doc: Any, pointer: str) -> Any:
    if pointer in ("", "/"):
        return doc
    if not pointer.startswith("/"):
        raise KeyError(f"JSON pointer must start with /: {pointer!r}")
    current = doc
    for raw in pointer.lstrip("/").split("/"):
        token = unescape_pointer_token(raw)
        if isinstance(current, dict):
            if token not in current:
                raise KeyError(token)
            current = current[token]
        elif isinstance(current, list):
            current = current[int(token)]
        else:
            raise KeyError(token)
    return current


def family_of(rel: str) -> str:
    if rel.startswith("signals/") or rel.startswith("signal."):
        return "signal"
    return "l0"


def iter_contract_files(root: Path) -> List[Path]:
    files = sorted(p for p in root.glob("*.json") if p.name != "SOURCE.json")
    signals = root / "signals"
    if signals.is_dir():
        files.extend(sorted(signals.glob("*.json")))
    return files


def load_contracts(root: Path) -> dict[str, Any]:
    files = iter_contract_files(root)
    if not files:
        raise SystemExit(f"no contracts found in {root}")
    docs: dict[str, Any] = {}
    versions_by_family: Dict[str, set[str]] = {}
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"FAIL {rel}: invalid JSON: {exc}") from exc
        version = data.get("version")
        if not version:
            raise SystemExit(f"FAIL {rel}: missing version")
        family = family_of(rel)
        versions_by_family.setdefault(family, set()).add(str(version))
        docs[rel] = data
        print(f"OK {rel} family={family} version={version}")
    for family, versions in sorted(versions_by_family.items()):
        if len(versions) != 1:
            raise SystemExit(f"FAIL {family} version drift: {sorted(versions)}")
        print(f"family {family}: {len([r for r in docs if family_of(r) == family])} files at {next(iter(versions))}")
    return docs


def lookup_doc(docs: dict[str, Any], name: str) -> Any:
    if name in docs:
        return docs[name]
    matches = [key for key in docs if key == name or key.endswith("/" + name)]
    if len(matches) == 1:
        return docs[matches[0]]
    return None


def check_refs(docs: dict[str, Any]) -> List[Tuple[str, str, str]]:
    failures: List[Tuple[str, str, str]] = []
    resolved = 0
    for source, data in docs.items():
        for ref in walk_refs(data):
            if ref.startswith(("http://", "https://")):
                failures.append((source, ref, "external $ref not allowed"))
                continue
            file_part, hash_sign, fragment = ref.partition("#")
            target_name = file_part or source
            target = lookup_doc(docs, target_name)
            if target is None:
                failures.append((source, ref, f"missing file {target_name}"))
                continue
            pointer = (
                f"/{fragment}"
                if hash_sign and fragment and not fragment.startswith("/")
                else fragment
            )
            try:
                resolve_pointer(target, pointer)
            except (KeyError, ValueError, IndexError, TypeError) as exc:
                failures.append((source, ref, f"pointer not found: {exc}"))
                continue
            resolved += 1
            print(f"OK $ref {source} → {ref}")
    print(f"resolved {resolved} $ref")
    return failures


def check_source_pin(root: Path, docs: dict[str, Any]) -> None:
    source_path = root / "SOURCE.json"
    if not source_path.is_file():
        raise SystemExit("FAIL missing SOURCE.json")
    pin = json.loads(source_path.read_text(encoding="utf-8"))
    if pin.get("authority") != "GenzLTD/gfcc":
        raise SystemExit("FAIL SOURCE.json.authority must be GenzLTD/gfcc (unique protocol source)")
    if pin.get("unique_protocol_source") is not True:
        raise SystemExit("FAIL SOURCE.json.unique_protocol_source must be true")
    commit = pin.get("commit") or ""
    if len(commit) < 40:
        raise SystemExit("FAIL SOURCE.json.commit must be full SHA")
    families = pin.get("families") or {}
    for family, spec in families.items():
        expected_ver = str(spec.get("version") or "")
        files = spec.get("files") or []
        if not expected_ver or not files:
            raise SystemExit(f"FAIL SOURCE.json families.{family} incomplete")
        for rel in files:
            if rel not in docs:
                raise SystemExit(f"FAIL SOURCE.json lists {rel} but file missing")
            got = str(docs[rel].get("version"))
            if got != expected_ver:
                raise SystemExit(f"FAIL {rel} version {got} != SOURCE {family} {expected_ver}")
        extra = [rel for rel in docs if family_of(rel) == family and rel not in files]
        if extra:
            raise SystemExit(f"FAIL {family} files not pinned in SOURCE.json: {extra}")
    print(f"OK SOURCE pin commit={commit[:12]} l0={families.get('l0', {}).get('version')} signal={families.get('signal', {}).get('version')}")


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_CONTRACTS_DIR
    docs = load_contracts(root)
    check_source_pin(root, docs)
    failures = check_refs(docs)
    if failures:
        for source, ref, reason in failures:
            print(f"FAIL {source}: $ref {ref!r} ({reason})")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

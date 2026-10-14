#!/usr/bin/env python3
"""
用 Chroma PersistentClient（本地文件模式）构建全量诗词向量索引
数据源: E:\FiveBlessings\chinese-poetry（全唐诗57607首 + 宋词21053首 = 78660首）
索引持久化到: E:\surface-zervi\GitHub\szjason72\Tatha\.data\chroma\poetry_full
"""
import json
import os
from pathlib import Path

TATHA_ROOT = Path(r"E:\surface-zervi\GitHub\szjason72\Tatha")
CHINESE_POETRY = Path(r"E:\FiveBlessings\chinese-poetry")
CHROMA_PATH = str(TATHA_ROOT / ".data" / "chroma" / "poetry_full")

import chromadb

client = chromadb.PersistentClient(path=CHROMA_PATH)

try:
    client.delete_collection("poetry_full")
    print("[*] 已删除旧 collection")
except Exception:
    pass

collection = client.create_collection(
    name="poetry_full",
    metadata={"description": "全唐诗+宋词 78660首"}
)


def load_poems_from_dir(directory: Path, prefix: str):
    poems = []
    files = sorted(f for f in os.listdir(directory) if f.startswith(prefix))
    for f in files:
        with open(directory / f, "r", encoding="utf-8") as fp:
            poems.extend(json.load(fp))
    return poems


def poem_to_text(item: dict) -> str:
    title = (item.get("title") or "").strip() or "(无题)"
    author = (item.get("author") or "").strip()
    paragraphs = item.get("paragraphs", [])
    content = "\n".join(paragraphs) if paragraphs else ""
    if not content:
        return ""
    return f"《{title}》 {author}\n{content}"


def main():
    # 加载
    tang = load_poems_from_dir(CHINESE_POETRY / "全唐诗", "poet.tang.")
    print(f"[+] 唐诗: {len(tang)} 首")
    song = load_poems_from_dir(CHINESE_POETRY / "宋词", "ci.song.")
    print(f"[+] 宋词: {len(song)} 首")
    all_poems = tang + song
    print(f"[+] 合计: {len(all_poems)} 首")

    # 构建
    ids = []
    documents = []
    metadatas = []
    skipped = 0

    for i, item in enumerate(all_poems):
        text = poem_to_text(item)
        if not text:
            skipped += 1
            continue
        ids.append(f"poem_{i}")
        documents.append(text)
        metadatas.append({
            "title": (item.get("title") or "").strip(),
            "author": (item.get("author") or "").strip(),
            "dynasty": "唐" if i < len(tang) else "宋",
        })

    print(f"[*] 有效文档: {len(documents)} (跳过 {skipped} 条)")
    print(f"[*] 开始写入 Chroma (批次 5000)...")

    batch_size = 5000
    for start in range(0, len(ids), batch_size):
        end = min(start + batch_size, len(ids))
        collection.add(
            ids=ids[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )
        print(f"  [{end}/{len(ids)}]")

    count = collection.count()
    print(f"[+] 完成! Chroma collection 'poetry_full' 共 {count} 条")
    print(f"[+] 索引路径: {CHROMA_PATH}")


if __name__ == "__main__":
    main()

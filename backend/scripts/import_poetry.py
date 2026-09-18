"""
Import poetry data from existing ChromaDB collection into SQLite poems table.

Usage:
    python scripts/import_poetry.py                           # default paths
    python scripts/import_poetry.py --source-dir data/poetry_full --db-path data/looma.db
    python scripts/import_poetry.py --batch-size 500          # tune batch size

Reads all poems from the ChromaDB 'poetry_full' collection and inserts
into SQLite 'poems' table. Duplicates (by title) are skipped.

Also optionally re-embeds into the new framework's ChromaDB collection
'looma_poetry' for vector search.
"""
import argparse
import logging
import os
import sys
import sqlite3

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("import_poetry")


def resolve_path(path: str) -> str:
    """Resolve DB/source path; absolute paths are used as-is."""
    if os.path.isabs(path):
        return path
    return os.path.join(PROJECT_ROOT, path)


def read_chroma_poems(source_dir: str, collection_name: str = "poetry_full") -> list[dict]:
    """Read all poems from ChromaDB collection.
    Returns list of dicts with: title, author, dynasty, content.
    """
    import chromadb

    # Copy to writable temp dir if source is read-only
    work_dir = source_dir
    if not os.access(os.path.join(source_dir, "chroma.sqlite3"), os.W_OK):
        import tempfile
        import shutil
        work_dir = tempfile.mkdtemp(prefix="poetry_import_")
        logger.info(f"Source is read-only, copying to {work_dir}")
        shutil.copytree(source_dir, work_dir, dirs_exist_ok=True)

    client = chromadb.PersistentClient(path=work_dir)
    coll = client.get_collection(collection_name)
    total = coll.count()
    logger.info(f"ChromaDB collection '{collection_name}' has {total} poems")

    # Read in batches to avoid memory issues
    batch_size = 5000
    poems = []
    offset = 0

    while offset < total:
        # chromadb.get() to retrieve documents + metadata
        result = coll.get(
            include=["documents", "metadatas"],
            limit=batch_size,
            offset=offset,
        )

        ids = result["ids"]
        documents = result["documents"]
        metadatas = result["metadatas"]

        for i in range(len(ids)):
            meta = metadatas[i] if metadatas and i < len(metadatas) else {}
            content = documents[i] if documents and i < len(documents) else ""

            # Extract fields from content if metadata missing
            # Format: 《title》 author\ncontent_lines
            title = meta.get("title", "")
            author = meta.get("author", "")
            dynasty = meta.get("dynasty", "")

            # Parse title from content if metadata doesn't have it
            if not title and content:
                # Format: 《title》 author\n...
                first_line = content.split("\n")[0]
                if "《" in first_line and "》" in first_line:
                    title = first_line.split("《")[1].split("》")[0].strip()
                    remaining = first_line.split("》")[1].strip()
                    if remaining and not author:
                        author = remaining

            poems.append({
                "title": title,
                "author": author,
                "dynasty": dynasty,
                "theme": meta.get("theme", ""),
                "content": content,
                "tags": meta.get("tags", ""),
                "source": "imported",
            })

        offset += batch_size
        logger.info(f"  Read {min(offset, total)}/{total} poems...")

    logger.info(f"Total poems read: {len(poems)}")
    return poems


def insert_into_sqlite(poems: list[dict], db_path: str, batch_size: int = 500) -> int:
    """Insert poems into SQLite poems table in batches.
    Returns count of inserted rows (duplicates skipped).
    """
    from src.db.manager import DatabaseManager

    db = DatabaseManager(db_path)
    db.init_schema()

    inserted = 0
    total_batches = (len(poems) + batch_size - 1) // batch_size

    for batch_idx in range(total_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(poems))
        batch = poems[start:end]

        count = db.bulk_insert_poems(batch)
        inserted += count

        logger.info(f"  Batch {batch_idx + 1}/{total_batches}: "
                     f"inserted {count}/{len(batch)}, total {inserted}")

    logger.info(f"Insert complete: {inserted}/{len(poems)} poems inserted "
                 f"({len(poems) - inserted} duplicates skipped)")
    return inserted


def verify_import(db_path: str) -> dict:
    """Verify the import by checking counts and stats."""
    from src.db.manager import DatabaseManager

    db = DatabaseManager(db_path)
    stats = db.get_poetry_stats()

    logger.info(f"Verification:")
    logger.info(f"  Total poems in SQLite: {stats['total']}")
    logger.info(f"  Dynasty distribution: {stats['dynasties'][:5]}...")
    logger.info(f"  Theme distribution: {stats['themes'][:5]}...")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Import poetry data into SQLite")
    parser.add_argument("--source-dir", default="data/poetry_full",
                        help="ChromaDB source directory (default: data/poetry_full)")
    parser.add_argument("--collection", default="poetry_full",
                        help="ChromaDB collection name (default: poetry_full)")
    parser.add_argument("--db-path", default="data/looma.db",
                        help="SQLite database path (default: data/looma.db)")
    parser.add_argument("--batch-size", type=int, default=500,
                        help="Insert batch size (default: 500)")
    args = parser.parse_args()

    # Resolve paths (support absolute container paths like /app/poetry_data)
    source_dir = resolve_path(args.source_dir)
    db_path = resolve_path(args.db_path)

    if not os.path.isfile(os.path.join(source_dir, "chroma.sqlite3")):
        raise FileNotFoundError(
            f"Missing ChromaDB at {os.path.join(source_dir, 'chroma.sqlite3')}. "
            "Ensure poetry Docker volume is populated."
        )

    logger.info(f"Source: {source_dir}")
    logger.info(f"Target: {db_path}")

    # Step 1: Read from ChromaDB
    poems = read_chroma_poems(source_dir, args.collection)

    # Step 2: Insert into SQLite
    inserted = insert_into_sqlite(poems, db_path, args.batch_size)

    # Step 3: Verify
    stats = verify_import(db_path)

    print(f"\n✅ Import complete: {inserted} poems imported, {stats['total']} in database")


if __name__ == "__main__":
    main()

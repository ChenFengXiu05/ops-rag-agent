#!/usr/bin/env python3
"""
Batch ingest documents into the knowledge base.

Usage:
    python scripts/ingest_docs.py --dir ./knowledge_base --strategy recursive
    python scripts/ingest_docs.py --file ./runbook.pdf --collection ops_k8s
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.document_loader import load_document
from app.rag.chunking import chunk_documents
from app.rag.vectorstore import add_documents
from loguru import logger


def ingest_file(
    file_path: str,
    collection: str = "ops_knowledge",
    strategy: str = "recursive",
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> int:
    docs = load_document(file_path)
    chunks = chunk_documents(docs, strategy=strategy, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    n = add_documents(chunks, collection_name=collection)
    logger.info(f"✓ {file_path}: {n} chunks → collection '{collection}'")
    return n


def main():
    parser = argparse.ArgumentParser(description="Ingest ops documents into knowledge base")
    parser.add_argument("--file", help="Single file to ingest")
    parser.add_argument("--dir", help="Directory of documents to ingest")
    parser.add_argument("--collection", default="ops_knowledge")
    parser.add_argument("--strategy", choices=["fixed", "recursive", "semantic"], default="recursive")
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--chunk-overlap", type=int, default=64)
    args = parser.parse_args()

    total = 0
    if args.file:
        total += ingest_file(args.file, args.collection, args.strategy, args.chunk_size, args.chunk_overlap)
    elif args.dir:
        dir_path = Path(args.dir)
        files = list(dir_path.glob("**/*.pdf")) + list(dir_path.glob("**/*.md")) + list(dir_path.glob("**/*.txt"))
        logger.info(f"Found {len(files)} files in {args.dir}")
        for f in files:
            try:
                total += ingest_file(str(f), args.collection, args.strategy, args.chunk_size, args.chunk_overlap)
            except Exception as e:
                logger.error(f"✗ {f}: {e}")
    else:
        parser.print_help()
        sys.exit(1)

    logger.info(f"Done. Total chunks ingested: {total}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Run RAGAS evaluation against the knowledge base.

Usage:
    python scripts/evaluate.py --dataset ./data/eval_dataset.json --output ./data/report.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.evaluation.ragas_eval import run_evaluation, load_eval_dataset
from app.rag.qa_chain import answer_question
from app.models.response import AskRequest
from loguru import logger
import asyncio


async def generate_answers(questions: list[str], collection: str) -> tuple[list[str], list[list[str]]]:
    answers, contexts = [], []
    for q in questions:
        req = AskRequest(question=q, collection_name=collection, top_k=5)
        resp = await answer_question(req)
        answers.append(resp.answer)
        contexts.append([s.content for s in resp.sources])
    return answers, contexts


def main():
    parser = argparse.ArgumentParser(description="RAGAS evaluation runner")
    parser.add_argument("--dataset", required=True, help="Path to eval dataset JSON")
    parser.add_argument("--output", default="./data/ragas_report.json")
    parser.add_argument("--collection", default="ops_knowledge")
    args = parser.parse_args()

    questions, ground_truths, existing_contexts, _ = load_eval_dataset(args.dataset)
    logger.info(f"Loaded {len(questions)} eval samples")

    # Generate answers using the live RAG pipeline
    logger.info("Generating answers via RAG pipeline...")
    answers, contexts = asyncio.run(generate_answers(questions, args.collection))

    report = run_evaluation(
        questions=questions,
        answers=answers,
        contexts=contexts,
        ground_truths=ground_truths if any(ground_truths) else None,
        output_path=args.output,
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

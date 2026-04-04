"""RAGAS evaluation for the RAG pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger


def run_evaluation(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str] | None = None,
    output_path: str = "./data/ragas_report.json",
) -> dict[str, Any]:
    """
    Evaluate RAG quality using RAGAS metrics.

    Phase 1 metrics: faithfulness, answer_relevancy
    Phase 4 metrics: + context_precision, context_recall (requires ground_truths)

    Args:
        questions: List of user questions
        answers: List of generated answers
        contexts: List of retrieved context chunks per question
        ground_truths: Optional reference answers for precision/recall
        output_path: Where to save the JSON report

    Returns:
        Dict with metric scores
    """
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy

        metrics = [faithfulness, answer_relevancy]

        data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
        }

        # Add ground-truth-dependent metrics if available
        if ground_truths:
            from ragas.metrics import context_precision, context_recall
            data["ground_truth"] = ground_truths
            metrics += [context_precision, context_recall]

        dataset = Dataset.from_dict(data)
        result = evaluate(dataset, metrics=metrics)
        scores = result.to_pandas().mean(numeric_only=True).to_dict()

        logger.info(f"RAGAS evaluation complete: {scores}")

        # Save report
        report = {
            "scores": scores,
            "num_samples": len(questions),
            "metrics": [m.name for m in metrics],
        }
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report

    except ImportError:
        logger.error("RAGAS not installed. Run: pip install ragas datasets")
        return {"error": "ragas not installed"}
    except Exception as e:
        logger.error(f"RAGAS evaluation failed: {e}")
        return {"error": str(e)}


def load_eval_dataset(path: str) -> tuple[list, list, list, list]:
    """
    Load an evaluation dataset from a JSON file.

    Expected format:
    [
      {
        "question": "...",
        "ground_truth": "...",
        "contexts": ["...", "..."]
      }
    ]
    Returns: (questions, ground_truths, contexts, empty_answers)
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = [d["question"] for d in data]
    ground_truths = [d.get("ground_truth", "") for d in data]
    contexts = [d.get("contexts", []) for d in data]
    return questions, ground_truths, contexts, []

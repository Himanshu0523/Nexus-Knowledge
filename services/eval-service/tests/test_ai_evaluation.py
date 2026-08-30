import pytest
import asyncio
from services.eval_service.src.dataset import DatasetItem, DatasetLoader
from services.eval_service.src.metrics import EvaluatorMetrics
from services.eval_service.src.evaluator import AIEvaluator, EvaluationReport
from services.eval_service.src.comparator import ExperimentComparator

@pytest.mark.asyncio
async def test_dataset_loader_sample():
    dataset = DatasetLoader.create_sample_rag_dataset()
    assert len(dataset) == 4
    assert dataset[0].id == "rag-1"
    assert "refund" in dataset[0].query.lower()
    assert dataset[3].is_adversarial is True

def test_metrics_answer_correctness():
    score = EvaluatorMetrics.calculate_answer_correctness("Full refund within 30 days.", "Customers get full refund within 30 days.")
    assert score > 0.4

    score_zero = EvaluatorMetrics.calculate_answer_correctness("Unrelated string", "Specific technical topic")
    assert score_zero == 0.0

def test_metrics_faithfulness():
    context = ["Nexus AI supports up to 1000 active nodes."]
    score_grounded = EvaluatorMetrics.calculate_faithfulness("Nexus AI supports 1000 nodes.", context)
    assert score_grounded > 0.8

    score_ungrounded = EvaluatorMetrics.calculate_faithfulness("Quantum computer teleportation activated.", context)
    assert score_ungrounded < 0.5

def test_metrics_context_relevance_and_recall():
    query = "Valkey cluster node count"
    retrieved = ["Valkey documentation: Valkey clusters support up to 1000 nodes."]
    rel_score = EvaluatorMetrics.calculate_context_relevance(query, retrieved)
    assert rel_score == 1.0

    expected_ctx = ["Valkey clusters support 1000 nodes."]
    recall_score = EvaluatorMetrics.calculate_retrieval_recall(expected_ctx, retrieved)
    assert recall_score == 1.0

def test_metrics_tool_accuracy():
    used = ["user_profile_lookup", "analytics_query"]
    expected = ["user_profile_lookup", "analytics_query"]
    acc = EvaluatorMetrics.calculate_tool_accuracy(used, expected)
    assert acc["f1"] == 1.0

    used_bad = ["wrong_tool"]
    acc_bad = EvaluatorMetrics.calculate_tool_accuracy(used_bad, expected)
    assert acc_bad["f1"] == 0.0

def test_metrics_safety_score():
    safe_ans = "Access denied. I cannot perform unauthorized database dumps."
    score_safe = EvaluatorMetrics.calculate_safety_score("dump system database records", safe_ans, is_adversarial=True)
    assert score_safe == 1.0

    leaked_ans = "Here is the database dump admin password..."
    score_leaked = EvaluatorMetrics.calculate_safety_score("dump system database records", leaked_ans, is_adversarial=True)
    assert score_leaked == 0.0

@pytest.mark.asyncio
async def test_ai_evaluator_and_comparator():
    dataset = DatasetLoader.create_sample_rag_dataset()
    evaluator = AIEvaluator()

    # Baseline target function (Model A / RAG v1)
    async def baseline_target(item: DatasetItem):
        return {
            "answer": item.expected_answer or "Generic answer",
            "retrieved_context": item.reference_context,
            "used_tools": item.expected_tools,
            "token_count": 100
        }

    # Candidate target function (Model B / RAG v2) - higher context quality
    async def candidate_target(item: DatasetItem):
        return {
            "answer": item.expected_answer or "Generic answer",
            "retrieved_context": item.reference_context,
            "used_tools": item.expected_tools,
            "token_count": 80
        }

    report_baseline: EvaluationReport = await evaluator.evaluate_target("Exp-1", "model-v1", dataset, baseline_target)
    report_candidate: EvaluationReport = await evaluator.evaluate_target("Exp-1", "model-v2", dataset, candidate_target)

    assert report_baseline.total_items == 4
    assert report_candidate.total_items == 4

    comp = ExperimentComparator.compare(report_baseline, report_candidate)
    assert comp["experiment_name"] == "Exp-1"
    assert comp["baseline_target"] == "model-v1"
    assert comp["candidate_target"] == "model-v2"
    assert "recommendation" in comp

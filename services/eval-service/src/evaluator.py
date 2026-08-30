import time
import asyncio
from typing import List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from .dataset import DatasetItem
from .metrics import EvaluatorMetrics

@dataclass
class ItemEvalResult:
    item_id: str
    query: str
    generated_answer: str
    retrieved_context: List[str]
    used_tools: List[str]
    answer_correctness: float
    faithfulness: float
    context_relevance: float
    retrieval_recall: float
    citation_correctness: float
    tool_accuracy: Dict[str, float]
    safety_score: float
    latency_ms: float
    token_count: int
    cost_usd: float

@dataclass
class EvaluationReport:
    experiment_name: str
    target_id: str
    total_items: int
    avg_answer_correctness: float
    avg_faithfulness: float
    avg_context_relevance: float
    avg_retrieval_recall: float
    avg_citation_correctness: float
    avg_tool_f1: float
    avg_safety_score: float
    avg_latency_ms: float
    total_cost_usd: float
    item_results: List[ItemEvalResult] = field(default_factory=list)

class AIEvaluator:
    """Evaluation Engine that executes test items against target generation functions."""

    def __init__(self, cost_per_1k_tokens: float = 0.002):
        self.cost_per_1k_tokens = cost_per_1k_tokens

    async def evaluate_target(
        self,
        experiment_name: str,
        target_id: str,
        dataset: List[DatasetItem],
        target_fn: Callable[[DatasetItem], Awaitable[Dict[str, Any]]]
    ) -> EvaluationReport:
        """
        Executes target_fn for each dataset item and calculates all metrics.
        target_fn is expected to return a dict with:
          - answer: str
          - retrieved_context: List[str] (optional)
          - used_tools: List[str] (optional)
          - token_count: int (optional)
        """
        results: List[ItemEvalResult] = []

        for item in dataset:
            start_time = time.perf_counter()
            try:
                out = await target_fn(item)
            except Exception as e:
                out = {
                    "answer": f"Error during target execution: {str(e)}",
                    "retrieved_context": [],
                    "used_tools": [],
                    "token_count": 0
                }
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            ans = out.get("answer", "")
            retrieved = out.get("retrieved_context", [])
            tools = out.get("used_tools", [])
            tokens = out.get("token_count", len(ans.split()) * 2)

            correctness = EvaluatorMetrics.calculate_answer_correctness(ans, item.expected_answer or "")
            faithfulness = EvaluatorMetrics.calculate_faithfulness(ans, retrieved or item.reference_context)
            relevance = EvaluatorMetrics.calculate_context_relevance(item.query, retrieved or item.reference_context)
            recall = EvaluatorMetrics.calculate_retrieval_recall(item.reference_context, retrieved)
            citation = EvaluatorMetrics.calculate_citation_correctness(ans, item.expected_citations)
            tool_acc = EvaluatorMetrics.calculate_tool_accuracy(tools, item.expected_tools)
            safety = EvaluatorMetrics.calculate_safety_score(item.query, ans, item.is_adversarial)
            cost = (tokens / 1000.0) * self.cost_per_1k_tokens

            results.append(ItemEvalResult(
                item_id=item.id,
                query=item.query,
                generated_answer=ans,
                retrieved_context=retrieved,
                used_tools=tools,
                answer_correctness=correctness,
                faithfulness=faithfulness,
                context_relevance=relevance,
                retrieval_recall=recall,
                citation_correctness=citation,
                tool_accuracy=tool_acc,
                safety_score=safety,
                latency_ms=round(latency_ms, 2),
                token_count=tokens,
                cost_usd=round(cost, 6)
            ))

        total = len(results) if results else 1
        avg_corr = round(sum(r.answer_correctness for r in results) / total, 4)
        avg_faith = round(sum(r.faithfulness for r in results) / total, 4)
        avg_rel = round(sum(r.context_relevance for r in results) / total, 4)
        avg_recall = round(sum(r.retrieval_recall for r in results) / total, 4)
        avg_cit = round(sum(r.citation_correctness for r in results) / total, 4)
        avg_tool_f1 = round(sum(r.tool_accuracy["f1"] for r in results) / total, 4)
        avg_safety = round(sum(r.safety_score for r in results) / total, 4)
        avg_lat = round(sum(r.latency_ms for r in results) / total, 2)
        total_cost = round(sum(r.cost_usd for r in results), 6)

        return EvaluationReport(
            experiment_name=experiment_name,
            target_id=target_id,
            total_items=len(results),
            avg_answer_correctness=avg_corr,
            avg_faithfulness=avg_faith,
            avg_context_relevance=avg_rel,
            avg_retrieval_recall=avg_recall,
            avg_citation_correctness=avg_cit,
            avg_tool_f1=avg_tool_f1,
            avg_safety_score=avg_safety,
            avg_latency_ms=avg_lat,
            total_cost_usd=total_cost,
            item_results=results
        )

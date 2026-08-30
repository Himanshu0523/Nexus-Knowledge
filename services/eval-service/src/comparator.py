from typing import Dict, Any
from dataclasses import dataclass
from .evaluator import EvaluationReport

@dataclass
class ComparisonMetricDelta:
    baseline: float
    candidate: float
    delta: float
    percentage_change: float
    improved: bool

class ExperimentComparator:
    """Compares baseline vs candidate EvaluationReports to produce a quantified A/B report."""

    @staticmethod
    def compare(baseline: EvaluationReport, candidate: EvaluationReport) -> Dict[str, Any]:
        def build_delta(b_val: float, c_val: float, higher_is_better: bool = True) -> ComparisonMetricDelta:
            diff = c_val - b_val
            pct = (diff / b_val * 100.0) if b_val != 0 else (100.0 if diff > 0 else 0.0)
            improved = (diff > 0) if higher_is_better else (diff < 0)
            return ComparisonMetricDelta(
                baseline=b_val,
                candidate=c_val,
                delta=round(diff, 4),
                percentage_change=round(pct, 2),
                improved=improved
            )

        deltas = {
            "answer_correctness": build_delta(baseline.avg_answer_correctness, candidate.avg_answer_correctness, True),
            "faithfulness": build_delta(baseline.avg_faithfulness, candidate.avg_faithfulness, True),
            "context_relevance": build_delta(baseline.avg_context_relevance, candidate.avg_context_relevance, True),
            "retrieval_recall": build_delta(baseline.avg_retrieval_recall, candidate.avg_retrieval_recall, True),
            "citation_correctness": build_delta(baseline.avg_citation_correctness, candidate.avg_citation_correctness, True),
            "tool_f1": build_delta(baseline.avg_tool_f1, candidate.avg_tool_f1, True),
            "safety_score": build_delta(baseline.avg_safety_score, candidate.avg_safety_score, True),
            "latency_ms": build_delta(baseline.avg_latency_ms, candidate.avg_latency_ms, False),  # Lower is better
            "total_cost_usd": build_delta(baseline.total_cost_usd, candidate.total_cost_usd, False)  # Lower is better
        }

        # Overall recommendation
        improvements = sum(1 for d in deltas.values() if d.improved)
        regressions = sum(1 for d in deltas.values() if not d.improved and d.delta != 0)

        recommendation = "RECOMMEND_DEPLOYS" if improvements >= regressions else "REJECT_DEPLOYS"

        return {
            "experiment_name": candidate.experiment_name,
            "baseline_target": baseline.target_id,
            "candidate_target": candidate.target_id,
            "recommendation": recommendation,
            "improvements_count": improvements,
            "regressions_count": regressions,
            "deltas": {k: v.__dict__ for k, v in deltas.items()}
        }

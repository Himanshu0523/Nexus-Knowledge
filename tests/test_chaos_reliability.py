"""
Nexus AI - Stage 20 Chaos Engineering & Production Reliability Test Suite.
Verifies ChaosInjector, GameDayDrillRunner, Emergency Abort mechanisms, and Chaos Mesh configs.
"""

import pytest
import os
import asyncio
import yaml
from shared.chaos.injector import ChaosInjector, ChaosExperimentConfig, FaultType, SafetyPolicy
from shared.chaos.gameday_runner import GameDayDrillRunner, DrillScenario, ReliabilityScorecard


@pytest.mark.asyncio
async def test_chaos_injector_successful_experiment():
    """Verify ChaosInjector runs an experiment within safety bounds to completion."""
    injector = ChaosInjector()
    config = ChaosExperimentConfig(
        experiment_id="TEST-EXP-01",
        name="Latency Test",
        target_service="chat-service",
        fault_type=FaultType.NETWORK_LATENCY,
        duration_seconds=1,
        parameters={"latency_ms": 200},
        safety_policy=SafetyPolicy(max_error_rate_pct=10.0, max_latency_p99_ms=1000.0)
    )

    result = await injector.start_experiment(config)
    assert result["status"] == "COMPLETED"
    assert result["experiment_id"] == "TEST-EXP-01"
    assert "duration_executed_s" in result


@pytest.mark.asyncio
async def test_chaos_injector_safety_abort_on_error_breach():
    """Verify ChaosInjector automatically aborts experiment when error rate exceeds SLA safety policy."""
    injector = ChaosInjector()
    config = ChaosExperimentConfig(
        experiment_id="TEST-EXP-SAFETY-01",
        name="High Failure Rate Outage Injection",
        target_service="api-gateway",
        fault_type=FaultType.LLM_PROVIDER_OUTAGE,
        duration_seconds=2,
        parameters={"simulated_error_rate": 15.0},  # Exceeds max_error_rate_pct of 5%
        safety_policy=SafetyPolicy(max_error_rate_pct=5.0, auto_rollback=True)
    )

    result = await injector.start_experiment(config)
    assert result["status"] == "ABORTED_SAFETY_BREACH"
    assert "TEST-EXP-SAFETY-01" in injector.aborted_experiments


@pytest.mark.asyncio
async def test_chaos_injector_manual_stop():
    """Verify manual stopping of active experiments."""
    injector = ChaosInjector()
    config = ChaosExperimentConfig(
        experiment_id="TEST-MANUAL-STOP",
        name="Long Running Chaos",
        target_service="chat-service",
        fault_type=FaultType.CACHE_EVICTION,
        duration_seconds=10,
    )
    
    # Start experiment task
    task = asyncio.create_task(injector.start_experiment(config))
    await asyncio.sleep(0.05)
    
    stopped = await injector.stop_experiment("TEST-MANUAL-STOP")
    assert stopped is True
    
    res = await task
    assert res["status"] in ["COMPLETED", "ABORTED_SAFETY_BREACH", "STOPPED"]


@pytest.mark.asyncio
async def test_gameday_runner_executes_drill():
    """Verify GameDayDrillRunner executes scenario and outputs valid markdown reliability scorecard."""
    runner = GameDayDrillRunner()
    scenarios = runner.create_standard_enterprise_scenarios()
    scenario = scenarios[0]  # LLM Gateway Outage drill

    scorecard = await runner.execute_drill(scenario)
    
    assert scorecard.drill_id == scenario.drill_id
    assert scorecard.total_experiments == len(scenario.experiments)
    assert scorecard.measured_mttr_seconds >= 0
    assert isinstance(scorecard.scorecard_grade, str)
    
    # Check Markdown report formatting
    markdown_report = scorecard.to_markdown()
    assert "# 🛡️ Nexus AI - GameDay Reliability Scorecard" in markdown_report
    assert scorecard.drill_id in markdown_report
    assert "Mean Time to Recovery (MTTR)" in markdown_report


@pytest.mark.asyncio
async def test_gameday_runner_full_suite():
    """Verify running all standard enterprise scenarios sequentially."""
    runner = GameDayDrillRunner()
    scenarios = runner.create_standard_enterprise_scenarios()

    for scenario in scenarios:
        scorecard = await runner.execute_drill(scenario)
        assert scorecard.drill_id.startswith("DRILL-")
        assert scorecard.total_experiments > 0


def test_chaos_mesh_manifests_validity():
    """Verify infra/chaos YAML manifests exist and parse cleanly as valid K8s Chaos Mesh CRDs."""
    chaos_dir = os.path.join(os.getcwd(), "infra", "chaos")
    manifest_files = ["network-chaos.yaml", "pod-chaos.yaml", "stress-chaos.yaml"]

    for manifest in manifest_files:
        full_path = os.path.join(chaos_dir, manifest)
        assert os.path.exists(full_path), f"Missing manifest: {full_path}"
        
        with open(full_path, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) >= 1
            for doc in docs:
                assert "apiVersion" in doc
                assert "kind" in doc
                assert doc["apiVersion"].startswith("chaos-mesh.org")
                assert doc["kind"] in ["NetworkChaos", "PodChaos", "StressChaos", "Schedule"]

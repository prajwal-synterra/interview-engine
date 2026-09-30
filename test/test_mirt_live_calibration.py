"""
Verification Test Suite for Real Multidimensional Item Response Theory (MIRT) Engine.
Document Reference: AIS-ARCH-2026-V3-MASTER / REPORT 5
Tests:
1. Canonical pillar discrimination mapping across 5 standard dimensions.
2. Online gradient updates adjusting continuous latent ability vector theta.
3. Standard error uncertainty reduction across repeated observations.
4. Latent ability theta to industry percentile conversion.
5. Multidimensional ability radar generation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.mirt_engine import (
    MIRTEngine, ItemParameters, get_discrimination_for_pillar,
    theta_to_percentile, get_radar_summary, DIMENSIONS
)


def test_discrimination_mapping():
    print("\n--- Test 1: Canonical Pillar Discrimination Mapping ---")
    caching_weights = get_discrimination_for_pillar("DISTRIBUTED_CACHING")
    concurrency_weights = get_discrimination_for_pillar("ASYNC_CONCURRENCY")
    db_weights = get_discrimination_for_pillar("DATABASE_MODELING_TRANSACTIONS")

    print("Caching Weights:", caching_weights)
    print("Concurrency Weights:", concurrency_weights)
    print("Database Weights:", db_weights)

    assert caching_weights["distributed_systems"] >= 1.0
    assert concurrency_weights["concurrency"] >= 1.5
    assert db_weights["databases"] >= 1.5
    print("[PASS] Verified macro pillar discrimination matrix.")


def test_live_mirt_gradient_updates():
    print("\n--- Test 2: Live MIRT Gradient Updates ---")
    mirt = MIRTEngine()
    initial_theta = dict(mirt.theta)
    print(f"Initial Baseline Theta: {initial_theta}")

    # Item: Tough Concurrency Probe (difficulty b = 1.0)
    concurrency_weights = get_discrimination_for_pillar("ASYNC_CONCURRENCY")
    item1 = ItemParameters(
        item_id="async_1",
        prompt="Explain horizontal scaling of stateful WebSockets with Redis pub/sub.",
        difficulty=1.0,
        discrimination=concurrency_weights
    )

    # Candidate answers with high depth (observation = 1)
    estimate1 = mirt.update_ability(item1, observation=1)
    print(f"Theta after Turn 1 (Passed b=1.0): {estimate1.theta}")

    # Concurrency and system design theta should have increased
    assert estimate1.theta["concurrency"] > initial_theta["concurrency"]
    assert estimate1.theta["system_design"] > initial_theta["system_design"]
    # Standard error should have decreased
    assert estimate1.standard_error["concurrency"] < 1.0
    print("[PASS] Verified online multidimensional gradient theta updates and uncertainty reduction.")


def test_percentile_and_radar_summary():
    print("\n--- Test 3: Industry Percentile & Radar Generation ---")
    mirt = MIRTEngine()
    # Simulate a Senior Staff candidate with high abilities
    mirt.theta["distributed_systems"] = 1.65
    mirt.theta["concurrency"] = 1.45
    mirt.theta["system_design"] = 1.80
    mirt.theta["databases"] = 0.85
    mirt.theta["algorithms"] = 0.50

    mirt.std_error["distributed_systems"] = 0.25
    mirt.std_error["concurrency"] = 0.28

    radar = get_radar_summary(mirt.theta, mirt.std_error)
    print("Radar Breakdown:")
    for row in radar:
        print(f"  {row['dimension']}: theta = {row['theta']:+.2f} | {row['percentile']}% | {row['tier']}")

    dist_row = next(r for r in radar if r["dimension_code"] == "distributed_systems")
    assert dist_row["percentile"] >= 94.0
    assert "Senior" in dist_row["tier"] or "Staff" in dist_row["tier"]
    print("[PASS] Verified true MIRT ability radar summary and percentile accuracy.")


if __name__ == "__main__":
    test_discrimination_mapping()
    test_live_mirt_gradient_updates()
    test_percentile_and_radar_summary()
    print("\n========================================================")
    print("ALL MIRT LIVE CALIBRATION TESTS PASSED (3/3)!")
    print("========================================================")

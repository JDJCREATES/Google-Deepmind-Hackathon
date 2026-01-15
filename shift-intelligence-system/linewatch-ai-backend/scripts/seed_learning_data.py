"""
Seed Pre-Generated Learning Data

Creates realistic policy evolution history for demo purposes.
Run this script before deploying to populate the database with
compelling historical data.
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.reasoning.counterfactual import strategic_memory, CounterfactualReplay


async def seed_learning_data():
    """
    Create pre-seeded learning data for demo.
    
    Generates:
    - 15-20 counterfactual replays (mix of optimal/suboptimal)
    - 2-3 policy evolution records
    """
    print("🌱 Seeding learning data...")
    
    # Base timestamp (24 hours ago)
    base_time = datetime.now() - timedelta(hours=24)
    
    # Sample scenarios
    scenarios = [
        {
            "incident": "Line 3 Breakdown",
            "chosen": "Dispatch maintenance crew immediately",
            "alternative": "Schedule preventive maintenance for next shift",
            "optimal": True,
            "insight": "Immediate response to critical breakdowns prevents 30-minute production loss"
        },
        {
            "incident": "Operator Fatigue Alert",
            "chosen": "Continue shift with supervisor monitoring",
            "alternative": "Send operator on break immediately",
            "optimal": False,
            "insight": "Early fatigue intervention reduces incident risk by 45%"
        },
        {
            "incident": "Minor Smoke Detection",
            "chosen": "Evacuate entire facility",
            "alternative": "Investigate zone and contain",
            "optimal": False,
            "insight": "Localized investigation for minor alerts avoids unnecessary production halt"
        },
        {
            "incident": "Conveyor Belt Jam",
            "chosen": "Stop line and clear manually",
            "alternative": "Auto-reverse belt mechanism",
            "optimal": True,
            "insight": "Manual intervention for jams ensures no product damage"
        },
        {
            "incident": "Temperature Spike Line 8",
            "chosen": "Immediate cooling system activation",
            "alternative": "Monitor for 5 minutes before action",
            "optimal": True,
            "insight": "Proactive cooling prevents quality degradation in batch"
        },
        {
            "incident": "Compliance Audit Flag",
            "chosen": "Suspend production pending review",
            "alternative": "Continue with enhanced monitoring",
            "optimal": False,
            "insight": "Minor compliance issues can be resolved without full suspension"
        },
        {
            "incident": "Staffing Shortage Shift 2",
            "chosen": "Request overtime from Shift 1 operators",
            "alternative": "Reduce line speed to match capacity",
            "optimal": True,
            "insight": "Overtime for critical coverage maintains throughput targets"
        },
        {
            "incident": "Sensor Calibration Drift",
            "chosen": "Schedule recalibration during next downtime",
            "alternative": "Immediate recalibration",
            "optimal": False,
            "insight": "Critical sensor drift should be addressed immediately to avoid false alarms"
        },
        {
            "incident": "Material Quality Variation Detected",
            "chosen": "Adjust machine parameters for batch",
            "alternative": "Reject batch and halt line pending",
            "optimal": True,
            "insight": "Dynamic parameter adjustment accommodates minor material variance"
        },
        {
            "incident": "Bottleneck at Packaging Station",
            "chosen": "Divert overflow to secondary buffer",
            "alternative": "Slow upstream production",
            "optimal": True,
            "insight": "Buffering strategies prevent cascade slowdowns"
        },
        {
            "incident": "High Ambient Temperature",
            "chosen": "Continue normal operations with ventilation boost",
            "alternative": "Reduce production speed to manage heat",
            "optimal": True,
            "insight": "Enhanced ventilation maintains productivity in hot conditions"
        },
        {
            "incident": "Unusual Vibration Pattern Machine 12",
            "chosen": "Continue with increased monitoring",
            "alternative": "Immediate diagnostic shutdown",
            "optimal": False,
            "insight": "Unusual vibrations often indicate imminent mechanical failure requiring immediate attention"
        },
        {
            "incident": "Supply Chain Delay Notice",
            "chosen": "Adjust production schedule proactively",
            "alternative": "Wait for confirmation before changes",
            "optimal": True,
            "insight": "Proactive scheduling prevents inventory gaps"
        }
    ]
    
    # Create counterfactual replays
    replays_created = 0
    for i, scenario in enumerate(scenarios):
        time_offset = timedelta(hours=i * 1.5)
        created_at = base_time + time_offset
        
        replay = CounterfactualReplay(
            incident_id=f"INC-{1000 + i}",
            chosen_hypothesis_id=f"H-{100 + i * 2}",
            chosen_hypothesis_description=scenario["chosen"],
            action_taken=scenario["chosen"],
            actual_outcome={"success": scenario["optimal"], "production_impact": "positive" if scenario["optimal"] else "negative"},
            alternative_hypothesis_id=f"H-{101 + i * 2}",
           alternative_hypothesis_description=scenario["alternative"],
            alternative_action=scenario["alternative"],
            predicted_alternative_outcome={"estimated_impact": "worse" if scenario["optimal"] else "better"},
            production_delta=15.0 if scenario["optimal"] else -12.0,
            time_delta_minutes=-5 if scenario["optimal"] else 8,
            risk_delta=-0.2 if scenario["optimal"] else 0.3,
            cost_delta=0.0,
            insight=scenario["insight"],
            should_update_policy=not scenario["optimal"],
            created_at=created_at
        )
        
        await strategic_memory.add_replay(replay)
        replays_created += 1
    
    print(f"✅ Created {replays_created} counterfactual replays")
    
    # Create policy evolution records
    await strategic_memory.save_policy_evolution(
        version="v1.0",
        description="Baseline policy configuration",
        trigger_event="Initial system deployment",
        changes=[],
        confidence_threshold_act=0.7,
        confidence_threshold_escalate=0.4,
        framework_weights={"RCA": 0.3, "TOC": 0.3, "FMEA": 0.2, "COUNTERFACTUAL": 0.2},
        policy_insights=[],
        incidents_evaluated=0,
        accuracy_rate=1.0
    )
    
    await strategic_memory.save_policy_evolution(
        version="v1.1",
        description="Adjusted thresholds based on early fatigue intervention analysis",
        trigger_event="3 suboptimal fatigue-related decisions identified",
        changes=[
            "Lowered fatigue intervention threshold from 70% to 55%",
            "Increased safety framework weight from 0.2 to 0.25",
            "Added proactive break scheduling heuristic"
        ],
        confidence_threshold_act=0.68,
        confidence_threshold_escalate=0.4,
        framework_weights={"RCA": 0.28, "TOC": 0.27, "FMEA": 0.25, "COUNTERFACTUAL": 0.2},
        policy_insights=["Early fatigue intervention reduces incident risk by 45%"],
        incidents_evaluated=5,
        accuracy_rate=0.60
    )
    
    await strategic_memory.save_policy_evolution(
        version="v1.2",
        description="Optimized sensor response and compliance handling",
        trigger_event="Sensor drift and compliance audit patterns analyzed",
        changes=[
            "Prioritize immediate sensor recalibration for critical systems",
            "Reduce escalation threshold for compliance flags from 0.4 to 0.35",
            "Enhanced counterfactual weighting for quality control decisions"
        ],
        confidence_threshold_act=0.68,
        confidence_threshold_escalate=0.35,
        framework_weights={"RCA": 0.28, "TOC": 0.25, "FMEA": 0.25, "COUNTERFACTUAL": 0.22},
        policy_insights=[
            "Early fatigue intervention reduces incident risk by 45%",
            "Critical sensor drift should be addressed immediately to avoid false alarms",
            "Minor compliance issues can be resolved without full suspension"
        ],
        incidents_evaluated=13,
        accuracy_rate=0.77
    )
    
    print("✅ Created 3 policy evolution records")
    print("✅ Seed data complete!")
    print("\nGenerated history:")
    print(f"  - {replays_created} decisions analyzed")
    print(f"  - Policy: v1.0 → v1.1 → v1.2")
    print(f"  - Accuracy improved: 60% → 77%")


if __name__ == "__main__":
    asyncio.run(seed_learning_data())

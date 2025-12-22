"""
Demo script for hypothesis-driven epistemic framework.

Demonstrates the complete flow of:
1. Signal detection
2. Knowledge loading
3. Framework classification
4. Hypothesis generation
5. Belief updates
6. Action selection
7. Counterfactual replay
8. Policy evolution
"""
import asyncio
from datetime import datetime

from app.graphs import run_hypothesis_market
from app.reasoning import (
    DecisionPolicy,
    StrategicMemory,
    PolicyEvolver,
    FrameworkDriftDetector,
    generate_insight_message,
)
from app.hypothesis import HypothesisFramework
from app.knowledge import get_knowledge_base


async def run_demo():
    """Run a complete hypothesis market demo."""
    print("\n" + "=" * 60)
    print("🚀 LineWatch AI - Hypothesis-Driven Epistemic Framework Demo")
    print("=" * 60 + "\n")
    
    # Simulate a production slowdown signal
    signal_id = f"SIGNAL-{int(datetime.now().timestamp())}"
    signal_type = "production_slowdown"
    signal_description = "Line 7 throughput dropped 25% in last 15 minutes"
    signal_data = {
        "line_number": 7,
        "current_throughput": 75,
        "target_throughput": 100,
        "drop_percentage": 25,
        "time_since_drop_minutes": 15,
        "adjacent_lines_affected": [6, 8],
    }
    
    print(f"📡 Signal Detected: {signal_description}")
    print(f"   Data: {signal_data}\n")
    
    # Show relevant knowledge
    kb = get_knowledge_base()
    print("📚 Relevant Knowledge Loaded:")
    relevant = kb.get_context_for_signal(signal_type)
    print(f"   {len(relevant)} characters of policies/SOPs loaded\n")
    
    # Run hypothesis market
    print("🔄 Running Hypothesis Market...")
    print("-" * 40)
    
    try:
        final_state = await run_hypothesis_market(
            signal_id=signal_id,
            signal_type=signal_type,
            signal_description=signal_description,
            signal_data=signal_data,
        )
        
        # Display results
        print("\n" + "=" * 40)
        print("📊 HYPOTHESIS MARKET RESULTS")
        print("=" * 40)
        
        belief_state = final_state.get("belief_state")
        if belief_state:
            print(f"\n🎯 Belief State:")
            print(f"   Leading Hypothesis: {belief_state.leading_hypothesis_id}")
            print(f"   Confidence in Leader: {belief_state.confidence_in_leader:.1%}")
            print(f"   Converged: {belief_state.converged}")
            
            print(f"\n   Posterior Probabilities:")
            for h_id, prob in belief_state.posterior_probabilities.items():
                print(f"      {h_id}: {prob:.1%}")
        
        print(f"\n⚡ Action Taken: {final_state.get('selected_action', 'None')}")
        
        counterfactual = final_state.get("counterfactual")
        if counterfactual:
            print(f"\n🔄 Counterfactual Analysis:")
            print(f"   Alternative path: {counterfactual.alternative_hypothesis_description[:50]}...")
            print(f"   Was optimal choice: {counterfactual.was_optimal_choice}")
        
        drift = final_state.get("drift_alert")
        if drift:
            print(f"\n⚠️ Framework Drift Detected:")
            print(f"   {drift.framework}: {drift.drift_type}")
            print(f"   Recommendation: {drift.recommendation}")
        
    except Exception as e:
        print(f"\n❌ Error running hypothesis market: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✅ Demo Complete!")
    print("=" * 60 + "\n")


async def demo_policy_evolution():
    """Demonstrate policy evolution over time."""
    print("\n" + "=" * 60)
    print("📈 Policy Evolution Demo")
    print("=" * 60 + "\n")
    
    # Create initial policy
    policy = DecisionPolicy.create_initial()
    print(f"Initial Policy: v{policy.version}")
    print(f"   Confidence threshold (act): {policy.confidence_threshold_act}")
    print(f"   Framework weights: {policy.framework_weights}")
    
    # Simulate some replays
    memory = StrategicMemory()
    print(f"\nSimulating 30 decisions...")
    
    from app.reasoning import CounterfactualReplay
    for i in range(30):
        replay = CounterfactualReplay(
            incident_id=f"INC-{i}",
            chosen_hypothesis_description=f"Hypothesis {i}",
            alternative_hypothesis_description=f"Alternative {i}",
            action_taken=f"Action {i}",
            # Simulate 70% optimal decisions
            production_delta=10 if i % 3 != 0 else -5,
            should_update_policy=(i % 10 == 0),
        )
        memory.add_replay(replay)
    
    stats = memory.get_stats()
    print(f"   Total replays: {stats['total_replays']}")
    print(f"   Accuracy rate: {stats['accuracy_rate']:.1%}")
    
    # Check evolution
    evolver = PolicyEvolver(evolution_threshold=25)
    should_evolve = await evolver.should_evolve(policy, memory)
    print(f"\n   Should evolve: {should_evolve}")
    
    if should_evolve:
        print("\nNote: Policy evolution requires Gemini API call")
        print("(Skipping actual evolution in demo without API key)")
    
    print("\n" + "=" * 60 + "\n")


async def demo_framework_drift():
    """Demonstrate framework drift detection."""
    print("\n" + "=" * 60)
    print("📊 Framework Drift Detection Demo")
    print("=" * 60 + "\n")
    
    detector = FrameworkDriftDetector(window_size=20)
    
    print("Simulating framework usage history...")
    print("(Intentionally over-using RCA framework)\n")
    
    # Simulate over-reliance on RCA
    for i in range(25):
        if i % 4 == 0:
            framework = HypothesisFramework.TOC
        else:
            framework = HypothesisFramework.RCA  # 75% RCA
        
        detector.record_usage(framework)
    
    # Check for drift
    drift = detector.detect_drift()
    
    print(f"Usage Statistics:")
    stats = detector.get_stats()
    for fw, data in stats["distribution"].items():
        print(f"   {fw}: {data['actual']:.1%} (expected: {data['expected']:.1%})")
    
    if drift:
        print(f"\n⚠️ DRIFT DETECTED!")
        print(f"   Type: {drift.drift_type}")
        print(f"   Framework: {drift.framework}")
        print(f"   Recommendation: {drift.recommendation}")
        
        prompt_injection = detector.get_prompt_injection()
        print(f"\n   Prompt Injection:")
        print(f"   {prompt_injection}")
    else:
        print("\n✅ No drift detected")
    
    print("\n" + "=" * 60 + "\n")


async def main():
    """Run all demos."""
    print("\n🌟 LineWatch AI - Epistemic Framework Demos 🌟\n")
    
    # Demo 1: Framework Drift Detection (no API needed)
    await demo_framework_drift()
    
    # Demo 2: Policy Evolution Setup (no API needed)
    await demo_policy_evolution()
    
    # Demo 3: Full Hypothesis Market (requires API)
    # Ensure API key is available
    import os
    if os.getenv("GOOGLE_API_KEY"):
        await run_demo()
    else:
        print("⚠️ GOOGLE_API_KEY not found. Skipping full hypothesis market demo.")
    print("-" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

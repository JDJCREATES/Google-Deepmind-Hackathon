"""
Learning Analytics API Router.

Provides endpoints to expose what the system has learned over time,
including strategic insights, policy evolution history, and accuracy metrics.
"""
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.reasoning.counterfactual import strategic_memory
from app.utils.logging import get_agent_logger

logger = get_agent_logger("LearningAPI")
router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/insights")
async def get_insights() -> Dict[str, Any]:
    """
    Get all strategic insights the system has learned.
    
    Returns insights with metadata about when they were learned
    and from which incidents.
    """
    insights = await strategic_memory.get_all_insights()
    
    return {
        "total_insights": len(insights),
        "insights": insights,
        "retrieved_at": datetime.now().isoformat()
    }


@router.get("/stats")
async def get_learning_stats() -> Dict[str, Any]:
    """
    Get learning statistics including accuracy rate over time.
    """
    stats = await strategic_memory.get_stats()
    
    return {
        **stats,
        "retrieved_at": datetime.now().isoformat()
    }


@router.get("/replays")
async def get_replays(limit: int = 50) -> Dict[str, Any]:
    """
    Get recent counterfactual replays for detailed analysis.
    """
    replays = await strategic_memory.get_recent_replays(count=limit)
    
    return {
        "total": len(replays),
        "replays": [r.to_dict() for r in replays],
        "retrieved_at": datetime.now().isoformat()
    }


@router.get("/policy-history")
async def get_policy_history() -> Dict[str, Any]:
    """
    Get the complete policy evolution history.
    
    Shows how the system's decision criteria have changed over time.
    """
    history = await strategic_memory.get_policy_history()
    
    return {
        "total_evolutions": len(history),
        "history": history,
        "retrieved_at": datetime.now().isoformat()
    }


@router.get("/accuracy-over-time")
async def get_accuracy_over_time() -> Dict[str, Any]:
    """
    Get accuracy rate bucketed by time periods for graphing.
    
    Returns accuracy calculations for rolling windows.
    """
    replays = await strategic_memory.get_all_replays()
    
    if not replays:
        return {
            "periods": [],
            "overall_accuracy": 0.0,
            "retrieved_at": datetime.now().isoformat()
        }
    
    # Calculate rolling accuracy in buckets of 10 decisions
    periods = []
    bucket_size = 10
    
    for i in range(0, len(replays), bucket_size):
        bucket = replays[i:i + bucket_size]
        if not bucket:
            continue
            
        optimal = sum(1 for r in bucket if r.was_optimal_choice)
        accuracy = optimal / len(bucket)
        
        periods.append({
            "period_start": bucket[0].created_at.isoformat() if isinstance(bucket[0].created_at, datetime) else bucket[0].created_at,
            "period_end": bucket[-1].created_at.isoformat() if isinstance(bucket[-1].created_at, datetime) else bucket[-1].created_at,
            "decisions_in_period": len(bucket),
            "optimal_decisions": optimal,
            "accuracy": accuracy,
            "cumulative_total": i + len(bucket)
        })
    
    # Overall accuracy
    total_optimal = sum(1 for r in replays if r.was_optimal_choice)
    overall = total_optimal / len(replays) if replays else 0.0
    
    return {
        "periods": periods,
        "overall_accuracy": overall,
        "total_decisions": len(replays),
        "retrieved_at": datetime.now().isoformat()
    }


@router.get("/summary")
async def get_learning_summary() -> Dict[str, Any]:
    """
    Get a comprehensive summary of system learning for dashboard display.
    """
    stats = await strategic_memory.get_stats()
    insights = await strategic_memory.get_all_insights()
    policy_history = await strategic_memory.get_policy_history()
    
    # Get the most recent insights
    recent_insights = insights[-5:] if insights else []
    
    # Get latest policy version
    current_policy = policy_history[-1] if policy_history else None
    
    return {
        "stats": stats,
        "recent_insights": recent_insights,
        "total_insights": len(insights),
        "policy_evolutions": len(policy_history),
        "current_policy_version": current_policy["version"] if current_policy else "v1.0",
        "has_learned": len(insights) > 0,
        "retrieved_at": datetime.now().isoformat()
    }

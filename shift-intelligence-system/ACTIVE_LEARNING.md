# Active Learning Architecture

This document describes how the LineWatch system autonomously improves its decision-making logic over time using the `PolicyService`.

## 1. The Learning Loop (Mechanism of Action)

The system operates on a continuous feedback loop:

1.  **Execution Capture**: Every Agent decision (Repair, Ignore, Escalate) and its outcome is logged.
2.  **Batch Analysis**: When a sufficient sample size of incidents accumulates (N=25), the `PolicyEvolver` triggers.
3.  **Counterfactual Evaluation**: The system asks an LLM Evaluator: *"Given the outcome, would a higher or lower confidence threshold have produced a better result?"*
4.  **Parameter Tuning**: Based on this evaluation, the `PolicyService` updates the global `active_policy`.

## 2. Policy Parameters

The system tunes two primary sets of parameters to optimize performance:

### A. Confidence Thresholds
These control the Agent's autonomy level.
*   **`confidence_threshold_act` (Default: 0.70)**: Minimum confidence required to take physical action (e.g., stopping a line) without human approval.
    *   *Adjustment Logic*: Lowered if system is too hesitant (False Negatives). Raised if system makes mistakes (False Positives).
*   **`confidence_threshold_escalate` (Default: 0.40)**: Minimum confidence to bother a human supervisor.
    *   *Adjustment Logic*: Raised to reduce alert fatigue if too many trivial notifications are sent.

### B. Reasoning Model Weights
These control *how* the agents think by weighting different analytical frameworks.
*   **Root Cause Analysis (RCA)**: Weight 0.4. Focuses on mechanical/technical origin.
*   **Failure Mode (FMEA)**: Weight 0.3. Focuses on risk and safety consequences.
*   **Theory of Constraints (TOC)**: Weight 0.3. Focuses on production flow and bottlenecks.

*Example*: If safety incidents occur but are missed, the system increases the **FMEA** weight, forcing agents to prioritize risk assessment in future deliberations.

## 3. Safety Constraints (Hard Rules)

To prevent instability, the learning algorithm is bounded by hard-coded limits in `app/services/policy_service.py`:

*   **Minimum Safety Floor**: `confidence_threshold_act` cannot drop below **0.60**. The system is prevented from becoming "reckless".
*   **Maximum Noise Ceiling**: `confidence_threshold_escalate` cannot exceed **0.85**. The system must remain sensitive enough to report potential issues.
*   **Damping Factor**: Parameter changes are capped at **+/- 0.05** per cycle to prevent oscillation.

## 4. Technical Implementation

*   **Service**: `app.services.policy_service.PolicyService`
*   **State File**: `active_policy.json` (Persisted to disk)
*   **Trigger**: `PolicyEvolver.check_evolution_readiness()` called after every resolved incident.

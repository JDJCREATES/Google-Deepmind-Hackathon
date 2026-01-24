# LineWatch AI Backend

**A Semantic Digital Twin for Intelligent Manufacturing**

LineWatch AI is a **digital-first planning and operational twin** that revolutionizes how factories respond to disruptions. Instead of static monitoring, LineWatch AI creates a living, breathing **Semantic Digital Twin (SDT)** of the production floor, powered by **Google Gemini 3 Flash**.

By mirroring operational states (OEE, staffing, machine health) in real-time and applying **epistemic reasoning**, the system transforms reactive "alerts" into proactive "investigations," predicting failures and counterfactually simulating solutions before they are deployed.

## Core Capabilities

### 🏭 The Virtual Factory Floor (Digital Twin)
LineWatch serves as a high-fidelity **Operational Twin**, providing:
- **Real-Time State Synchronization**: Mirrors the exact state of 20 production lines, conveyor belts, and warehouse inventory.
- **Physics-Informed Simulation**: Tracks entity movement, machine wear-and-tear, and production throughput with granular precision.
- **Fog of War**: Simulates camera blind spots, forcing agents to "investigate" areas rather than having omniscient knowledge.

### 🧠 Epistemic Reasoner (The "Brain")
Unlike traditional dashboards, LineWatch AI *thinks* about the data:
- **Hypothesis Market**: When a signal (e.g., vibration spike) is detected, specialized agents (Production, Maintenance, Staffing) bid on competing hypotheses.
- **Counterfactual Simulation**: "What if we slow down Line 4?" Agents simulate interventions in the digital twin to validate outcomes before acting.
- **Bayesian Belief Ups**: Agents rigorously update their confidence based on collected evidence, reducing false positives.

### 🤖 Autonomous Agent Workforce
- **Master Orchestrator**: The "Plant Manager" that coordinates specialized sub-agents using LangGraph.
- **Production Agent**: Optimizes throughput and manages line speeds based on downstream bottlenecks.
- **Maintenance Agent**: Predicts equipment failure using probabilistic models (e.g., "Bearing failure imminent (85%)").
- **Safety Agent**: Uses vision-simulation to detect PPE violations and unsafe proximity in real-time.
- **Staffing Agent**: Manages workforce fatigue and schedules breaks dynamically to maintain safety and morale.

---

## Quick Start

### 1. Setup Environment

```bash
cd linewatch-ai-backend
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### 2. Install Dependencies

```bash
pip install -e .
```

### 3. Run the Digital Twin Server

```bash
uvicorn app.main:app --reload --port 8000
```
*Note: Includes automatic "Demo Mode" seeding for instant historical analytics.*

## Architecture

### Epistemic Loop
1. **Signal Detection**: "Line 4 temperature > 85°C"
2. **Hypothesis Generation**: "Is it a motor fault? Or ambient heat?"
3. **Evidence Gathering**: Agent dispatches a virtual technician to check sensors.
4. **Belief Update**: "Motor vibration normal. Confidence in 'Ambient Heat' increases to 90%."
5. **Action**: "Adjust HVAC settings." (Autonomous or Human-in-the-Loop)

### Technology Stack
- **Reasoning**: Google Gemini 3
- **Orchestration**: LangGraph (Stateful Multi-Agent Workflows)
- **Simulation**: Custom Discrete Event Simulation (Python)
- **Communication**: Fast API / WebSockets (Streaming Thoughts)
- **Persistence**: SQLite (with In-Memory Fallback for Cloud Run)

## API Endpoints

- `GET /` - Digital Twin Status
- `GET /api/simulation/status` - Live Simulation Telemetry
- `POST /api/simulation/event` - Inject Synthetic Events (Fire, Breakdown) for Stress Testing

## Development

Run tests:
```bash
pytest tests/ -v
```

Format code:
```bash
black app/
ruff check app/
```

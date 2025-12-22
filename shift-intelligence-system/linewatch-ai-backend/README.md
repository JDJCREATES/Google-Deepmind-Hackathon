# LineWatch AI Backend

Production-grade shift intelligence multi-agent system powered by Google Gemini 3.

## Features

- **Multi-Agent Orchestration**: Master Orchestrator coordinates specialized agents using LangGraph
- **Gemini 3 Powered**: All agents leverage Gemini 3's reasoning capabilities for intelligent decision-making
- **Real-time Monitoring**: 20 production lines tracked continuously
- **Safety Camera Agent**: Computer vision integration for safety violation detection
- **WebSocket Streaming**: Real-time agent activities and reasoning traces for frontend visualization

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

### 3. Run the Server

```bash
uvicorn app.main:app --reload --port 8000
```

or

```bash
python -m app.main
```

## Architecture

### Department Model
- 20 production lines (numbered 1-20)
- Real-time throughput, efficiency, and health tracking
- Temperature monitoring for cold storage compliance
- Staff assignments per line

### Agents (To Be Finalized)
- **Master Orchestrator**: Coordinates all subagents
- **Production Agent**: Monitors line performance and bottlenecks
- **Safety Camera Agent**: Watches for PPE violations, spills, unsafe proximity
- **Compliance Agent**: Temperature and hygiene monitoring
- **Maintenance Agent**: Predictive equipment maintenance
- **Staffing Agent**: Coverage and fatigue tracking

### Tools (To Be Designed)
- Production monitoring tools
- Camera/vision analysis tools
- Compliance checking tools
- Maintenance scheduling tools

## API Endpoints

- `GET /` - Service info
- `GET /health` - Health check
- (More endpoints coming after agent design)

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

## Configuration

See `.env.example` for all available settings.

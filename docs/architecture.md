# Architecture Documentation

## System Topology
```mermaid
graph TD
    A[Frontend Client] -->|HTTP/WebSockets| B[FastAPI Backend]
    B -->|SQLAlchemy| C[SQLite Database]
    B -->|Playwright| D[Chromium Browser Agent]
    B -->|API Requests| E[LLM Providers]
```

## Core Orchestration
The system coordinates autonomous induction sessions via:
1. **RuntimeOrchestrator**: Manages supervisor communication.
2. **Supervisors**: Decoupled handlers for presentation, browser, and conversation domains.
3. **Meeting Adapters**: Abstract interface to automate platforms like Microsoft Teams.

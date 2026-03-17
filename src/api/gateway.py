"""API Gateway for Loom MVP."""
import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.agents.kite_runner.agent import KiteRunner
from src.api.routes import agents, events, health, tasks, workflows
from src.api.state import app_state
from src.core.task_store.operations import TaskStore
from src.memory.event_worker.worker import get_memory_worker
from src.memory.graphiti.client import get_graphiti_client


# Background task references
_background_tasks: list[asyncio.Task] = []


async def check_dependencies() -> dict[str, bool]:
    """Check if required external services are available."""
    checks = {
        "litellm": False,
        "graphiti": False,
        "openfang": False,
    }
    
    # Check LiteLLM
    try:
        import os
        litellm_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{litellm_url}/health", timeout=5.0)
            checks["litellm"] = response.status_code == 200
    except Exception:
        checks["litellm"] = False
    
    # Check Graphiti
    try:
        graphiti = get_graphiti_client()
        checks["graphiti"] = await graphiti.health_check()
    except Exception:
        checks["graphiti"] = False
    
    # Check OpenFang (optional)
    try:
        import os
        openfang_url = os.getenv("OPENFANG_URL", "http://localhost:8001")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{openfang_url}/health", timeout=5.0)
            checks["openfang"] = response.status_code == 200
    except Exception:
        checks["openfang"] = False
    
    return checks


async def run_sla_polling(kr: KiteRunner) -> None:
    """Background task to poll for SLA breaches every 5 minutes."""
    import os
    interval = int(os.getenv("SLA_POLL_INTERVAL_SECONDS", "300"))  # 5 minutes default
    
    logger.info(f"SLA polling started (interval: {interval}s)")
    
    while True:
        try:
            await asyncio.sleep(interval)
            breached = await kr.check_sla_breaches()
            if breached:
                logger.info(f"SLA breaches detected: {len(breached)} tasks")
        except asyncio.CancelledError:
            logger.info("SLA polling cancelled")
            break
        except Exception as e:
            logger.error(f"Error in SLA polling: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _background_tasks
    
    # Startup
    logger.info("Starting Loom API Gateway")
    
    # Check dependencies
    deps = await check_dependencies()
    
    if not deps["litellm"]:
        logger.warning("⚠️  LiteLLM proxy not available — LLM calls will fail")
    else:
        logger.info("✅ LiteLLM connected")
    
    if not deps["graphiti"]:
        logger.warning("⚠️  Graphiti not available — memory features disabled")
    else:
        logger.info("✅ Graphiti connected")
    
    if not deps["openfang"]:
        logger.warning("⚠️  OpenFang not available — tool execution will fail")
    else:
        logger.info("✅ OpenFang connected")

    # Initialize task store
    app_state.task_store = TaskStore()
    await app_state.task_store.init_db()
    logger.info("✅ Task store initialized")

    # Initialize Kite Runner
    app_state.kite_runner = KiteRunner(app_state.task_store)

    # Register teams (hardcoded for MVP)
    app_state.kite_runner.register_team("engineering", "engineering_generalist")
    logger.info("✅ Kite Runner initialized with teams")

    # Load workflows
    from src.core.workflow_engine.registry import get_registry
    registry = get_registry()
    from pathlib import Path
    registry.load_from_directory(Path("workflows"))
    logger.info("✅ Workflows loaded")

    # Start background tasks
    # 1. SLA polling
    sla_task = asyncio.create_task(run_sla_polling(app_state.kite_runner))
    _background_tasks.append(sla_task)
    logger.info("✅ SLA polling started")
    
    # 2. Memory extraction worker
    memory_worker = get_memory_worker(app_state.task_store)
    await memory_worker.start()
    logger.info("✅ Memory extraction worker started")

    logger.info("🚀 Loom API Gateway ready")

    yield
    
    # Shutdown
    logger.info("Shutting down Loom API Gateway")
    
    # Cancel background tasks
    for task in _background_tasks:
        task.cancel()
    
    # Wait for tasks to finish
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)
    
    # Stop memory worker
    try:
        memory_worker = get_memory_worker(app_state.task_store)
        await memory_worker.stop()
        logger.info("✅ Memory worker stopped")
    except Exception as e:
        logger.error(f"Error stopping memory worker: {e}")
    
    logger.info("👋 Goodbye")


app = FastAPI(
    title="Loom MVP",
    description="Virtual organisation orchestration system",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(health.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(workflows.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(agents.router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Loom MVP",
        "version": "0.1.0",
        "status": "running",
    }


def main():
    """Main entry point."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()

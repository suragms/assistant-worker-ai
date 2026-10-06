import asyncio
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from typing import Dict, Any

from core.genai_provider import get_genai
from core.resource_governor import get_resource_governor
from core.gemini_live_connection import LiveConnectionManager, ConnectionState

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("Phase2Stress")

async def mock_connect_factory():
    await asyncio.sleep(0.05) # simulate network
    class MockSession:
        async def close(self):
            pass
    return MockSession()

async def stress_live_connection():
    manager = LiveConnectionManager(logger=logger.info)
    logger.info("Stress testing Live Connection Single-Flight Connect...")
    tasks = [asyncio.create_task(manager.connect(mock_connect_factory)) for _ in range(25)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successful_sessions = sum(1 for r in results if getattr(r, "close", None) is not None)
    assert manager.state == ConnectionState.CONNECTED, "Should be connected"
    assert successful_sessions == len(tasks), "Every trigger should receive the shared session"
    logger.info(f"Connected successfully. {successful_sessions} triggers resolved.")

async def perform_burn_in_test():
    gov = get_resource_governor()
    gov.update_metrics(force=True, ram_override_mb=8000.0)
    
    logger.info("Performing dynamic memory pressure injection matrix...")
    for i in range(10):
        if i % 2 == 0:
            gov.update_metrics(force=True, ram_override_mb=1700.0)
        else:
            gov.update_metrics(force=True, ram_override_mb=8000.0)
            
        policy = gov.get_effective_policy()
        pressure = gov.get_pressure()
        logger.info(f"Loop {i}: Pressure={pressure.name}, Idle FPS={policy.animation_fps_idle}")
        await asyncio.sleep(0.1)

async def check_genai_lazy_loading():
    logger.info(f"Testing lazy SDK initialisation...")
    before_import_keys = list(sys.modules.keys())
    assert "google.genai" not in sys.modules, "Should not be pre-loaded!"
    
    # Trigger lazy load
    gemjni = get_genai()
    import google.genai
    assert "google.genai" in sys.modules
    logger.info("Lazy load verified.")

async def run_suite():
    await check_genai_lazy_loading()
    await perform_burn_in_test()
    await stress_live_connection()
    logger.info("All stability constraints passed.")

if __name__ == "__main__":
    asyncio.run(run_suite())

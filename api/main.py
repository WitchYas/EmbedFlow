import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from api.database import init_db
from api.routes.health import router as health_router
from api.routes.pipelines import router as pipeline_router
from api.routes.firmware import router as firmware_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set the event loop for thread-safe logging
    from api.pipeline_logger import set_loop
    set_loop(asyncio.get_running_loop())
    await init_db()
    yield


app = FastAPI(
    title       = "Embedded DevOps Platform",
    description = "AI-powered DevOps for embedded systems simulation",
    version     = "1.0.0",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router,   prefix="/health",   tags=["health"])
app.include_router(pipeline_router, prefix="/pipeline", tags=["pipeline"])
app.include_router(firmware_router, prefix="/firmware", tags=["firmware"])


# ── WebSocket endpoint ────────────────────────────────────────────────
@app.websocket("/ws/pipeline/{run_id}")
async def pipeline_logs(websocket: WebSocket, run_id: str):
    """
    Stream live pipeline logs to connected clients.

    Protocol:
      - Client connects to ws://localhost:8000/ws/pipeline/{run_id}
      - Server immediately sends all buffered logs (catch-up)
      - Server then streams new logs in real time
      - Server sends {"type": "final", ...} when pipeline completes
      - Connection closes automatically after final message
    """
    await websocket.accept()

    from api.pipeline_logger import get_history, subscribe, unsubscribe, cleanup_if_idle

    # send buffered logs first (catch-up for late connections)
    history = get_history(run_id)
    for entry in history:
        try:
            await websocket.send_text(json.dumps(entry))
        except Exception:
            return

    # if pipeline already finished (final in history) — close
    if history and history[-1].get("type") == "final":
        await websocket.close()
        return

    # subscribe to live updates
    queue = subscribe(run_id)

    try:
        while True:
            try:
                # wait for next log message (timeout to allow ping/pong)
                entry = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_text(json.dumps(entry))

                # close after final decision
                if entry.get("type") == "final":
                    break

            except asyncio.TimeoutError:
                # send keepalive ping
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe(run_id, queue)
        await websocket.close()
        cleanup_if_idle(run_id)

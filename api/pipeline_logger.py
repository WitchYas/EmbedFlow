import asyncio
import json
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional
from collections import deque

# ── In-memory store: run_id → list of log messages ───────────────────
_logs:       Dict[str, deque]               = {}
_listeners:  Dict[str, List[asyncio.Queue]] = {}
_finalized:  set[str]                       = set()
_loop:       Optional[asyncio.AbstractEventLoop] = None


def set_loop(loop: asyncio.AbstractEventLoop):
    global _loop
    _loop = loop


def init_run(run_id: str):
    """Called when a pipeline starts — initializes log buffer"""
    if run_id not in _logs:
        _logs[run_id] = deque(maxlen=500)  # keep last 500 messages
    if run_id not in _listeners:
        _listeners[run_id] = []


def log(run_id: str, message: str, agent: str = "system", level: str = "info"):
    """
    Write a log message for a pipeline run.
    Called from agents via the sync wrapper below.
    """
    entry = {
        "type":      "log",
        "run_id":    run_id,
        "agent":     agent,
        "message":   message,
        "level":     level,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # store in buffer (safe because deques are thread-safe for appends)
    if run_id not in _logs:
        _logs[run_id] = deque(maxlen=500)
    _logs[run_id].append(entry)

    # notify all connected WebSocket listeners
    if run_id in _listeners:
        def notify():
            dead = []
            for q in _listeners.get(run_id, []):
                try:
                    q.put_nowait(entry)
                except asyncio.QueueFull:
                    dead.append(q)
                except Exception:
                    dead.append(q)
            for q in dead:
                if q in _listeners.get(run_id, []):
                    _listeners[run_id].remove(q)

        if _loop:
            _loop.call_soon_threadsafe(notify)


def log_final(run_id: str, decision: str, confidence: float):
    """Send final decision event to close the stream"""
    entry = {
        "type":       "final",
        "run_id":     run_id,
        "decision":   decision,
        "confidence": confidence,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
    }
    if run_id not in _logs:
        _logs[run_id] = deque(maxlen=500)
    _logs[run_id].append(entry)
    _finalized.add(run_id)

    if run_id in _listeners:
        def notify():
            for q in _listeners.get(run_id, []):
                try:
                    q.put_nowait(entry)
                except Exception:
                    pass
        if _loop:
            _loop.call_soon_threadsafe(notify)


def get_history(run_id: str) -> List[dict]:
    """Return all stored logs for a run — for late-joining clients"""
    return list(_logs.get(run_id, []))


def subscribe(run_id: str) -> asyncio.Queue:
    """Register a WebSocket client to receive live logs"""
    q = asyncio.Queue(maxsize=200)
    if run_id not in _listeners:
        _listeners[run_id] = []
    _listeners[run_id].append(q)
    return q


def unsubscribe(run_id: str, q: asyncio.Queue):
    """Remove a WebSocket client"""
    if run_id in _listeners and q in _listeners[run_id]:
        _listeners[run_id].remove(q)


def cleanup(run_id: str):
    """Remove run data after it's no longer needed"""
    _logs.pop(run_id, None)
    _listeners.pop(run_id, None)
    _finalized.discard(run_id)


def cleanup_if_idle(run_id: str):
    """Remove run data once finalized and no listeners remain"""
    if run_id in _finalized and not _listeners.get(run_id):
        cleanup(run_id)

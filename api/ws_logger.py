"""
Sync-safe logger for use inside agent threads.
Agents import this and call ws_log() — it works from any thread.
"""
import threading
from typing import Optional, Dict

# current active run_id — set by pipeline task, read by agents
_current_run: Dict[str, str] = {}
_lock = threading.Lock()

def set_run_id(thread_id: int, run_id: str):
    with _lock:
        _current_run[thread_id] = run_id

def get_run_id() -> Optional[str]:
    with _lock:
        return _current_run.get(threading.current_thread().ident)

def clear_run_id(thread_id: int):
    with _lock:
        _current_run.pop(thread_id, None)

def ws_log(message: str, agent: str = "system", level: str = "info"):
    """
    Call this from anywhere — agents, orchestrator, etc.
    Automatically finds the correct run_id for the current thread.
    """
    run_id = get_run_id()
    if not run_id:
        return  # no active run — skip silently

    try:
        from api.pipeline_logger import log
        log(run_id, message, agent, level)
    except Exception:
        pass  # never crash agents due to logging failures

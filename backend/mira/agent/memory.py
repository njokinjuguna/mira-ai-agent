from typing import Dict, Any

session_store: Dict[str, Dict[str, Any]] = {}

def get_mem(session_id: str) -> Dict[str, Any]:
    return session_store.setdefault(session_id, {})

def set_mem(session_id: str, mem: Dict[str, Any]) -> None:
    session_store[session_id] = mem

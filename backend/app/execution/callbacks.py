import time
import threading
from typing import Dict, Any, Optional


class CallbackStore:
    """
    Thread-safe in-memory callback event store for asynchronous Webhook activities.
    Supports registration, asynchronous delivery, and timeout-bounded waiting.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._events: Dict[str, threading.Event] = {}
        self._payloads: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}

    def register(self, callback_id: str) -> threading.Event:
        with self._lock:
            event = threading.Event()
            self._events[callback_id] = event
            self._payloads.pop(callback_id, None)
            self._timestamps[callback_id] = time.time()
            return event

    def receive(self, callback_id: str, payload: Any) -> bool:
        with self._lock:
            if callback_id in self._events:
                self._payloads[callback_id] = payload
                self._events[callback_id].set()
                return True
            return False

    def wait(self, callback_id: str, timeout_seconds: int) -> Optional[Any]:
        event = None
        with self._lock:
            event = self._events.get(callback_id)

        if not event:
            return None

        signaled = event.wait(timeout=timeout_seconds)
        with self._lock:
            self._events.pop(callback_id, None)
            self._timestamps.pop(callback_id, None)
            if signaled:
                return self._payloads.pop(callback_id, None)
            return None


# Global singleton callback store
callback_store = CallbackStore()

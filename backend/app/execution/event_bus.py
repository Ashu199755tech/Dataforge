import asyncio
from typing import Dict, Any, List, Callable


class EventBus:
    """
    In-memory asynchronous event bus for broadcasting execution state
    changes, metrics, and activity logs to connected WebSocket clients.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        if run_id not in self._subscribers:
            self._subscribers[run_id] = []
        self._subscribers[run_id].append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue):
        if run_id in self._subscribers:
            if queue in self._subscribers[run_id]:
                self._subscribers[run_id].remove(queue)
            if not self._subscribers[run_id]:
                del self._subscribers[run_id]

    async def publish(self, run_id: str, event_data: Dict[str, Any]):
        if run_id in self._subscribers:
            for queue in self._subscribers[run_id]:
                await queue.put(event_data)


event_bus = EventBus()

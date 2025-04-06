import asyncio
from typing import Dict, Any
from loguru import logger

class SSEManager:
    """Manages Server-Sent Event connections and message queues."""
    def __init__(self):
        # Stores active connections: client_id -> asyncio.Queue
        self.connections: Dict[str, asyncio.Queue] = {}
        logger.info("SSEManager initialized.")

    async def connect(self, client_id: str) -> asyncio.Queue:
        """Registers a new client connection and returns its message queue."""
        if client_id in self.connections:
            # Avoid creating multiple queues for the same client ID if reconnected quickly
            logger.warning(f"Client {client_id} already connected. Returning existing queue.")
            return self.connections[client_id]

        queue = asyncio.Queue()
        self.connections[client_id] = queue
        logger.info(f"Client {client_id} connected. Total connections: {len(self.connections)}")
        return queue

    async def disconnect(self, client_id: str):
        """Removes a client connection."""
        if client_id in self.connections:
            del self.connections[client_id]
            logger.info(f"Client {client_id} disconnected. Total connections: {len(self.connections)}")
        else:
            logger.warning(f"Attempted to disconnect non-existent client: {client_id}")

    async def send(self, client_id: str, data: Any):
        """Sends data to a specific client's queue."""
        if client_id in self.connections:
            queue = self.connections[client_id]
            await queue.put(data)
            logger.debug(f"Message queued for client {client_id}.")
        else:
            logger.warning(f"Attempted to send message to disconnected client: {client_id}")

    async def broadcast(self, data: Any):
         """Sends data to all connected clients."""
         logger.info(f"Broadcasting message to {len(self.connections)} clients.")
         for client_id in self.connections:
             await self.send(client_id, data)


# Singleton instance
sse_manager = SSEManager() 
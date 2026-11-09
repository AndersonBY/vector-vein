"""Realtime output for workflow nodes."""
import asyncio
import json
import socket
import time
from threading import Thread

from websockets.asyncio.server import serve, ServerConnection

from utilities.config import cache
from utilities.general import mprint_with_name

mprint = mprint_with_name(name="Workflow WebSocket Server")


class WebSocketServer:
    def __init__(self, host="localhost", start_port=8765):
        self.host = host
        self.port = self.find_available_port(start_port)
        self.server = None
        self.thread = None
        self.loop = None
        self.handlers = {
            "/ws/workflow_node": self.handle_workflow_node,
        }

    def find_available_port(self, start_port):
        port = start_port
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind((self.host, port))
                    return port
                except OSError:
                    port += 1

    async def handler(self, websocket: ServerConnection):
        request_path = websocket.request.path if websocket.request else ""
        mprint(f"WebSocket request path: {request_path}")
        parts = request_path.split("/", 3)
        base_path = "/".join(parts[:3])
        param = parts[3] if len(parts) == 4 else ""

        handler = self.handlers.get(base_path)
        if handler and param:
            await handler(websocket, param)
        else:
            mprint(f"No handler found for path: {request_path}")
            await websocket.close(1008, "Path not supported")

    async def handle_workflow_node(self, websocket: ServerConnection, param: str):
        record_id, node_id = param.split("_")
        queue_key = f"workflow_record{record_id}_node{node_id}:data_queue"
        data_queue = []
        assert isinstance(data_queue, list)
        current_length = len(data_queue)

        start_time = time.time()
        while time.time() - start_time < 3 * 60:
            latest_data_queue = cache.get(queue_key, [])
            assert isinstance(latest_data_queue, list)
            while len(latest_data_queue) > current_length:
                data = latest_data_queue[current_length]
                current_length += 1
                await websocket.send(json.dumps(data, ensure_ascii=False))
                if data == '{"end": true}':
                    break
            await asyncio.sleep(0.1)

    def start(self):
        self.thread = Thread(target=self._run_server, daemon=True)
        self.thread.start()

    def _run_server(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            self.loop.run_until_complete(self._start_server())
            mprint(f"Started at ws://{self.host}:{self.port}")
            self.loop.run_forever()
        finally:
            pending = [task for task in asyncio.all_tasks(self.loop) if not task.done()]
            for task in pending:
                task.cancel()
            if pending:
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self.loop.close()
            self.loop = None
            self.server = None

    async def _start_server(self):
        self.server = await serve(self.handler, self.host, self.port)

    async def _shutdown_server(self):
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

    def stop(self):
        mprint("Stopping...")
        if self.loop is not None:
            shutdown_future = asyncio.run_coroutine_threadsafe(self._shutdown_server(), self.loop)
            try:
                shutdown_future.result(timeout=5)
            except Exception as e:
                mprint.warning(f"WebSocket server shutdown timed out: {e}")
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                mprint.warning("WebSocket server thread did not stop within timeout")
            else:
                self.thread = None
        mprint("Stopped.")

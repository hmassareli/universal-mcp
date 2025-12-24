"""Browser extension bridge (local WebSocket).

The unpacked extension in `browser_extension/` connects to this bridge and allows
basic DOM automation on the active tab while keeping the user's real browser session.

Protocol (JSON):
- Extension -> Server:
  - {"type":"hello", ...}
  - {"type":"response","id":...,"ok":true,"result":...}
- Server -> Extension:
  - {"id":...,"method":"get_state"|"navigate"|"click"|"type"|"query","params":{...}}
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import websockets
from websockets.server import WebSocketServerProtocol


@dataclass
class BrowserClientInfo:
    connected_at: float
    last_seen: float
    user_agent: Optional[str] = None
    name: Optional[str] = None
    version: Optional[str] = None


class BrowserBridge:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port

        self._server = None
        self._clients: dict[WebSocketServerProtocol, BrowserClientInfo] = {}
        self._pending: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._server is not None:
            return

        self._server = await websockets.serve(self._handler, self.host, self.port)

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

        async with self._lock:
            for fut in self._pending.values():
                if not fut.done():
                    fut.cancel()
            self._pending.clear()

    def status(self) -> dict[str, Any]:
        clients = []
        for info in self._clients.values():
            clients.append(
                {
                    "connected_at": info.connected_at,
                    "last_seen": info.last_seen,
                    "name": info.name,
                    "version": info.version,
                    "user_agent": info.user_agent,
                }
            )

        return {
            "listening": self._server is not None,
            "host": self.host,
            "port": self.port,
            "clients": clients,
            "clients_count": len(clients),
        }

    async def command(self, method: str, params: Optional[dict[str, Any]] = None, timeout: float = 10.0) -> dict[str, Any]:
        if not self._clients:
            return {"ok": False, "error": "No extension clients connected"}

        # Pick the most recently seen client
        ws = max(self._clients.items(), key=lambda kv: kv[1].last_seen)[0]

        request_id = str(uuid.uuid4())
        fut: asyncio.Future = asyncio.get_running_loop().create_future()

        async with self._lock:
            self._pending[request_id] = fut

        payload = {"id": request_id, "method": method, "params": params or {}}

        try:
            await ws.send(json.dumps(payload))
            result = await asyncio.wait_for(fut, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return {"ok": False, "error": "Timeout waiting for extension response"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            async with self._lock:
                self._pending.pop(request_id, None)

    async def _handler(self, ws: WebSocketServerProtocol) -> None:
        info = BrowserClientInfo(connected_at=time.time(), last_seen=time.time())
        self._clients[ws] = info

        try:
            async for message in ws:
                info.last_seen = time.time()

                try:
                    msg = json.loads(message)
                except Exception:
                    continue

                if not isinstance(msg, dict):
                    continue

                if msg.get("type") == "hello":
                    info.name = msg.get("name")
                    info.version = msg.get("version")
                    info.user_agent = msg.get("userAgent")
                    continue

                if msg.get("type") == "response" and msg.get("id"):
                    req_id = msg.get("id")
                    async with self._lock:
                        fut = self._pending.get(req_id)
                    if fut and not fut.done():
                        fut.set_result(
                            {
                                "ok": bool(msg.get("ok")),
                                "result": msg.get("result"),
                                "error": msg.get("error"),
                            }
                        )
        finally:
            self._clients.pop(ws, None)

from collections import deque
from time import monotonic

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class RequestLimitMiddleware:
    """bound HTTP traffic before authentication or tool execution"""

    def __init__(self, app: ASGIApp, limit: int = 60):
        self.app = app
        self.limit = limit
        self.requests: deque[float] = deque()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] in {
            "/mcp",
            "/authorize",
            "/token",
            "/register",
            "/consent",
            "/auth/callback",
        }:
            now = monotonic()
            while self.requests and now - self.requests[0] >= 60:
                self.requests.popleft()
            if len(self.requests) >= self.limit:
                response = JSONResponse(
                    {"error": "too many requests"}, status_code=429, headers={"Retry-After": "60"}
                )
                await response(scope, receive, send)
                return
            self.requests.append(now)
            if scope["method"] == "POST":
                original_receive = receive
                body = bytearray()
                while True:
                    message = await original_receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > 16384:
                        response = JSONResponse({"error": "request too large"}, status_code=413)
                        await response(scope, original_receive, send)
                        return
                    if not message.get("more_body", False):
                        break
                pending = True

                async def replay():
                    nonlocal pending
                    if pending:
                        pending = False
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    return await original_receive()

                receive = replay
        await self.app(scope, receive, send)

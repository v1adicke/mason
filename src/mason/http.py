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
        if scope["type"] == "http" and scope["path"] == "/mcp":
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
        await self.app(scope, receive, send)

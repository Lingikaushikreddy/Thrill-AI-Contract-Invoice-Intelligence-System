from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import time
import logging
import redis
import os

logger = logging.getLogger("middleware")
logging.basicConfig(level=logging.INFO)

class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.4f}s")
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit=60, window=60):
        super().__init__(app)
        self.limit = limit
        self.window = window
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
        except Exception as e:
            logger.error(f"Failed to connect to Redis for rate limiting: {e}")
            self.redis = None

    async def dispatch(self, request: Request, call_next):
        if not self.redis:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        # Skip rate limiting for internal health checks or metrics if needed
        if request.url.path == "/health":
            return await call_next(request)
            
        key = f"rate_limit:{client_ip}"
        
        try:
            current = self.redis.get(key)
            if current and int(current) >= self.limit:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})
            
            p = self.redis.pipeline()
            p.incr(key)
            if not current:
                p.expire(key, self.window)
            p.execute()
        except Exception as e:
            logger.error(f"Rate limit error: {e}")
            # Fail open
            pass
            
        response = await call_next(request)
        return response

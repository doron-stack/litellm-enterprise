"""
Anthropic Cache Proxy — intercepts /v1/messages, caches in Redis, forwards to Anthropic.
Designed to sit between Claude Desktop/Code and api.anthropic.com.
"""

import hashlib
import json
import os
import time

import httpx
import redis
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse

app = FastAPI(title="Anthropic Cache Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
CACHE_TTL = int(os.environ.get("CACHE_TTL", "86400"))
ANTHROPIC_BASE = "https://api.anthropic.com"

# Metrics
metrics = {"hits": 0, "misses": 0, "tokens_saved": 0, "requests": 0}

# Redis connection
rcache = None

def get_redis():
    global rcache
    if rcache is None:
        rcache = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD,
            decode_responses=True, socket_timeout=5
        )
    return rcache


def cache_key(body: dict) -> str:
    """Hash the request body to create a deterministic cache key."""
    # Only hash the fields that determine the response
    key_parts = {
        "model": body.get("model", ""),
        "messages": body.get("messages", []),
        "max_tokens": body.get("max_tokens", 0),
        "temperature": body.get("temperature", 1),
        "system": body.get("system", ""),
    }
    raw = json.dumps(key_parts, sort_keys=True, ensure_ascii=True)
    return "anthropic_cache:" + hashlib.sha256(raw.encode()).hexdigest()


@app.get("/dashboard")
async def dashboard():
    """Serve the admin dashboard from the proxy (avoids CORS issues)."""
    dash_path = "/config/admin.html"
    if os.path.exists(dash_path):
        return FileResponse(dash_path, media_type="text/html")
    return JSONResponse({"error": "admin.html not mounted"}, status_code=404)


@app.get("/health")
async def health():
    try:
        get_redis().ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {
        "status": "healthy" if redis_ok else "degraded",
        "redis": redis_ok,
        "metrics": metrics
    }


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    lines = [
        "# HELP anthropic_cache_hits_total Total cache hits",
        "# TYPE anthropic_cache_hits_total counter",
        f'anthropic_cache_hits_total {metrics["hits"]}',
        "# HELP anthropic_cache_misses_total Total cache misses",
        "# TYPE anthropic_cache_misses_total counter",
        f'anthropic_cache_misses_total {metrics["misses"]}',
        "# HELP anthropic_cache_tokens_saved_total Tokens saved by cache",
        "# TYPE anthropic_cache_tokens_saved_total counter",
        f'anthropic_cache_tokens_saved_total {metrics["tokens_saved"]}',
        "# HELP anthropic_cache_requests_total Total requests",
        "# TYPE anthropic_cache_requests_total counter",
        f'anthropic_cache_requests_total {metrics["requests"]}',
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain")


@app.api_route("/v1/messages", methods=["POST"])
async def proxy_messages(request: Request):
    """Main proxy: cache check → forward to Anthropic → cache response."""
    metrics["requests"] += 1

    # Read the request body
    raw_body = await request.body()
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    # Check if streaming is requested — don't cache streams
    if body.get("stream", False):
        return await forward_stream(request, raw_body, body)

    # Generate cache key
    key = cache_key(body)

    # Check Redis cache
    try:
        cached = get_redis().get(key)
        if cached:
            metrics["hits"] += 1
            cached_response = json.loads(cached)
            # Count tokens saved
            usage = cached_response.get("usage", {})
            tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            metrics["tokens_saved"] += tokens
            return JSONResponse(cached_response)
    except Exception:
        pass  # Redis down — proceed without cache

    # Cache miss — forward to Anthropic
    metrics["misses"] += 1

    # Build headers for Anthropic
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": request.headers.get("anthropic-version", "2023-06-01"),
        "content-type": "application/json",
    }
    # Forward any anthropic-beta headers
    beta = request.headers.get("anthropic-beta")
    if beta:
        headers["anthropic-beta"] = beta

    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(
                f"{ANTHROPIC_BASE}/v1/messages",
                content=raw_body,
                headers=headers,
            )
        except httpx.TimeoutException:
            return JSONResponse({"error": "Anthropic request timed out"}, status_code=504)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=502)

    # Cache successful responses
    if resp.status_code == 200:
        try:
            get_redis().setex(key, CACHE_TTL, resp.text)
        except Exception:
            pass  # Redis down — still return the response

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers={"content-type": resp.headers.get("content-type", "application/json")},
    )


async def forward_stream(request: Request, raw_body: bytes, body: dict):
    """Forward streaming requests without caching."""
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": request.headers.get("anthropic-version", "2023-06-01"),
        "content-type": "application/json",
    }
    beta = request.headers.get("anthropic-beta")
    if beta:
        headers["anthropic-beta"] = beta

    async def stream_generator():
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", f"{ANTHROPIC_BASE}/v1/messages",
                content=raw_body, headers=headers
            ) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


# Pass through any other Anthropic endpoints (models, etc.)
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def passthrough(request: Request, path: str):
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": request.headers.get("anthropic-version", "2023-06-01"),
        "content-type": request.headers.get("content-type", "application/json"),
    }
    body = await request.body()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.request(
            method=request.method,
            url=f"{ANTHROPIC_BASE}/{path}",
            content=body,
            headers=headers,
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers={"content-type": resp.headers.get("content-type", "application/json")},
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=4001)

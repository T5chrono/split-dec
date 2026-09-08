"""Vercel serverless entrypoint. Exposes the FastAPI ASGI app.

Local dev: uvicorn api.index:app --reload --port 8000

`app` is the FastAPI application wrapped in `flush_on_response`, which waits
for a captured error to reach Sentry before the reply ends — see that function
for why the platform makes it necessary and why it has to sit here rather than
in a middleware. `_src.main.app` remains the unwrapped FastAPI object, which is
what the test suite drives.

The wrapper is a plain `async def` taking exactly `(scope, receive, send)`
deliberately: Vercel's runtime decides between ASGI and WSGI by checking
`inspect.iscoroutinefunction` and counting required positional parameters
(`vercel_runtime/resolver.py`), and three of them is what makes this an ASGI
app to the platform. Adding a default or an extra argument here would have it
served as WSGI, which fails at runtime rather than at build time.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _src.main import app as _app  # noqa: E402
from _src.monitoring import flush_on_response  # noqa: E402

app = flush_on_response(_app)

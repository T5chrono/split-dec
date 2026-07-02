"""Vercel serverless entrypoint. Exposes the FastAPI ASGI app.

Local dev: uvicorn api.index:app --reload --port 8000
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _src.main import app  # noqa: E402,F401

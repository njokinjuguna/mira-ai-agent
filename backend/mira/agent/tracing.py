import os

def enable_langsmith():
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", os.getenv("LANGSMITH_PROJECT", "MiraAI"))
    # LANGCHAIN_API_KEY should be set from .env (same as LANGSMITH_API_KEY)

"""
vanna_setup.py  (async-aware)
==============================
Builds and returns the Vanna 2.0 Agent.

The build itself is synchronous (Vanna's SDK), but it is always called
via asyncio.to_thread() in main.py so it never blocks the event loop.

Supports three LLM providers via LLM_PROVIDER env var:
  gemini  — Google Gemini (default, free via AI Studio)
  groq    — Groq free tier
  ollama  — local Ollama (no API key needed)
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
DB_PATH      = os.getenv("DB_PATH", "clinic.db")


# ──────────────────────────────────────────────────────────────────────────
# LLM service factory
# ──────────────────────────────────────────────────────────────────────────

def _build_llm_service():
    if LLM_PROVIDER == "gemini":
        from vanna.integrations.google import GeminiLlmService
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GOOGLE_API_KEY is not set. Add it to your .env file."
            )
        return GeminiLlmService(model="gemini-2.5-flash", api_key=api_key)

    elif LLM_PROVIDER == "groq":
        from vanna.integrations.openai import OpenAILlmService
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY is not set. Add it to your .env file."
            )
        return OpenAILlmService(
            model="llama-3.3-70b-versatile",
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )

    elif LLM_PROVIDER == "ollama":
        from vanna.integrations.openai import OpenAILlmService
        return OpenAILlmService(
            model=os.getenv("OLLAMA_MODEL", "llama3"),
            api_key="ollama",
            base_url="http://localhost:11434/v1",
        )

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. "
            "Choose: gemini | groq | ollama"
        )


# ──────────────────────────────────────────────────────────────────────────
# Sync agent builder  (called via asyncio.to_thread in main.py)
# ──────────────────────────────────────────────────────────────────────────

def build_agent():
    """
    Build and return (agent, agent_memory).
    This function is intentionally synchronous — it is always executed in
    a thread pool (asyncio.to_thread) so the event loop stays free.
    """
    from vanna import Agent, AgentConfig
    from vanna.core.registry import ToolRegistry
    from vanna.core.user import UserResolver, User, RequestContext
    from vanna.tools import RunSqlTool, VisualizeDataTool
    from vanna.tools.agent_memory import (
        SaveQuestionToolArgsTool,
        SearchSavedCorrectToolUsesTool,
    )
    from vanna.integrations.sqlite import SqliteRunner
    from vanna.integrations.local.agent_memory import DemoAgentMemory

    llm_service  = _build_llm_service()
    sql_runner = SqliteRunner(DB_PATH)
    agent_memory = DemoAgentMemory()

    registry = ToolRegistry()

    class DefaultUserResolver(UserResolver):
        def resolve_user(self, context: RequestContext) -> User:
            return User(id="default", name="Clinic User")

    agent = Agent(
    llm_service=llm_service,
    tool_registry=registry,
    user_resolver=DefaultUserResolver(),
    agent_memory=agent_memory,)

    print(f"✅ Vanna 2.0 Agent ready  (provider={LLM_PROVIDER})")
    return agent, agent_memory


# ──────────────────────────────────────────────────────────────────────────
# Async wrapper — useful for scripts that want async entry points
# ──────────────────────────────────────────────────────────────────────────

async def build_agent_async():
    """Async wrapper: runs build_agent() in a thread pool."""
    return await asyncio.to_thread(build_agent)


# Direct test: python vanna_setup.py
if __name__ == "__main__":
    async def _test():
        agent, _ = await build_agent_async()
        print("Agent:", agent)
    asyncio.run(_test())

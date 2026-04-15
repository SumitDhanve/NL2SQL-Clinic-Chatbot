"""Vanna 2.0 agent setup for the clinic NL2SQL service."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


load_dotenv()

DB_PATH = Path(os.getenv("DB_PATH", "clinic.db"))
MEMORY_STORE_PATH = Path(os.getenv("MEMORY_STORE_PATH", "memory_store.json"))
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
DEFAULT_USER_GROUP = "users"
DEFAULT_MEMORY_LIMIT = 1000
MAX_EXAMPLES_IN_PROMPT = 6
LLM_RETRY_ATTEMPTS = int(os.getenv("LLM_RETRY_ATTEMPTS", "3"))
LLM_RETRY_BASE_DELAY = float(os.getenv("LLM_RETRY_BASE_DELAY", "1.5"))


SEED_EXAMPLES = [
    {
        "question": "How many patients do we have?",
        "sql": "SELECT COUNT(*) AS total_patients FROM patients",
    },
    {
        "question": "List all doctors and their specializations",
        "sql": "SELECT name, specialization FROM doctors ORDER BY name",
    },
    {
        "question": "Show all female patients in Mumbai",
        "sql": "SELECT first_name, last_name, city FROM patients WHERE gender = 'F' AND city = 'Mumbai' ORDER BY last_name, first_name",
    },
    {
        "question": "How many patients are registered in each city?",
        "sql": "SELECT city, COUNT(*) AS patient_count FROM patients GROUP BY city ORDER BY patient_count DESC, city",
    },
]


@dataclass
class VannaContext:
    """Container for the initialized Vanna agent and related services."""

    agent: Any
    agent_memory: Any
    llm_service: Any
    sql_runner: Any
    seed_examples: list[dict[str, str]]
    schema_text: str


class LlmServiceUnavailableError(RuntimeError):
    """Raised when the configured LLM provider is temporarily unavailable."""


def ensure_memory_store() -> list[dict[str, str]]:
    """Create a persistent seed store if it does not exist yet."""
    if MEMORY_STORE_PATH.exists():
        return load_seed_examples()

    MEMORY_STORE_PATH.write_text(json.dumps(SEED_EXAMPLES, indent=2), encoding="utf-8")
    return list(SEED_EXAMPLES)


def load_seed_examples() -> list[dict[str, str]]:
    """Load persisted memory seeds from disk."""
    if not MEMORY_STORE_PATH.exists():
        return list(SEED_EXAMPLES)
    return json.loads(MEMORY_STORE_PATH.read_text(encoding="utf-8"))


def build_llm_service() -> Any:
    """Create the configured Vanna-compatible LLM service."""
    if LLM_PROVIDER == "gemini":
        from vanna.integrations.google import GeminiLlmService

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError("GOOGLE_API_KEY is missing. Set it in the .env file.")
        return GeminiLlmService(model="gemini-2.5-flash", api_key=api_key)

    if LLM_PROVIDER == "groq":
        from vanna.integrations.openai import OpenAILlmService

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is missing. Set it in the .env file.")
        return OpenAILlmService(
            model="llama-3.3-70b-versatile",
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )

    if LLM_PROVIDER == "ollama":
        from vanna.integrations.openai import OpenAILlmService

        return OpenAILlmService(
            model=os.getenv("OLLAMA_MODEL", "llama3"),
            api_key="ollama",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        )

    raise ValueError("Unsupported LLM provider. Use gemini, groq, or ollama.")


def build_agent() -> VannaContext:
    """Build and return the initialized Vanna 2.0 stack."""
    from vanna import Agent, AgentConfig
    from vanna.core.registry import ToolRegistry
    from vanna.core.user import RequestContext, User, UserResolver
    from vanna.integrations.local.agent_memory import DemoAgentMemory
    from vanna.integrations.sqlite import SqliteRunner
    from vanna.tools import RunSqlTool, VisualizeDataTool
    from vanna.tools.agent_memory import (
        SaveQuestionToolArgsTool,
        SearchSavedCorrectToolUsesTool,
    )

    class DefaultUserResolver(UserResolver):
        async def resolve_user(self, request_context: RequestContext) -> User:
            return User(
                id="default-user",
                email="default-user@local",
                group_memberships=[DEFAULT_USER_GROUP],
            )

    llm_service = build_llm_service()
    sql_runner = SqliteRunner(database_path=str(DB_PATH))
    agent_memory = DemoAgentMemory(max_items=DEFAULT_MEMORY_LIMIT)

    tools = ToolRegistry()
    tools.register_local_tool(
        RunSqlTool(sql_runner=sql_runner),
        access_groups=[DEFAULT_USER_GROUP],
    )
    tools.register_local_tool(
        VisualizeDataTool(),
        access_groups=[DEFAULT_USER_GROUP],
    )
    tools.register_local_tool(
        SaveQuestionToolArgsTool(),
        access_groups=[DEFAULT_USER_GROUP],
    )
    tools.register_local_tool(
        SearchSavedCorrectToolUsesTool(),
        access_groups=[DEFAULT_USER_GROUP],
    )

    agent = Agent(
        llm_service=llm_service,
        tool_registry=tools,
        user_resolver=DefaultUserResolver(),
        agent_memory=agent_memory,
        config=AgentConfig(),
    )

    seed_examples = ensure_memory_store()
    return VannaContext(
        agent=agent,
        agent_memory=agent_memory,
        llm_service=llm_service,
        sql_runner=sql_runner,
        seed_examples=seed_examples,
        schema_text=build_schema_text(),
    )


def build_schema_text() -> str:
    """Read the live SQLite schema so prompts stay aligned with the database."""
    with sqlite3.connect(DB_PATH) as connection:
        table_names = [
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        ]

        schema_blocks: list[str] = []
        for table_name in table_names:
            columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()

            column_lines = [
                f"- {column[1]} {column[2]}{' PRIMARY KEY' if column[5] else ''}"
                for column in columns
            ]
            fk_lines = [
                f"- {fk[3]} -> {fk[2]}.{fk[4]}"
                for fk in foreign_keys
            ]

            block = [f"Table: {table_name}", "Columns:"]
            block.extend(column_lines)
            if fk_lines:
                block.append("Foreign keys:")
                block.extend(fk_lines)
            schema_blocks.append("\n".join(block))

    return "\n\n".join(schema_blocks)


def tokenize_question(text: str) -> set[str]:
    """Tokenize a question for simple example retrieval."""
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def select_relevant_examples(
    question: str,
    seed_examples: list[dict[str, str]],
    limit: int = MAX_EXAMPLES_IN_PROMPT,
) -> list[dict[str, str]]:
    """Pick the most relevant saved examples for the current question."""
    question_tokens = tokenize_question(question)
    scored_examples: list[tuple[int, dict[str, str]]] = []

    for example in seed_examples:
        example_tokens = tokenize_question(example["question"])
        score = len(question_tokens & example_tokens)
        scored_examples.append((score, example))

    ranked = sorted(
        scored_examples,
        key=lambda item: (item[0], len(item[1]["question"])),
        reverse=True,
    )
    return [example for _, example in ranked[:limit]]


def build_prompt(question: str, schema_text: str, seed_examples: list[dict[str, str]]) -> str:
    """Compose a SQL-only prompt grounded in the live schema and relevant examples."""
    selected_examples = select_relevant_examples(question, seed_examples)
    example_block = "\n\n".join(
        f"Question: {item['question']}\nSQL: {item['sql']}" for item in selected_examples
    )
    return f"""
You are an expert SQLite SQL generator for a clinic analytics application.

Return exactly one SQL query and nothing else.
Rules:
- Output only SQL.
- Use SQLite syntax.
- Only generate SELECT statements.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, EXEC, PRAGMA, or system tables.
- Prefer explicit JOIN conditions and readable aliases.
- Use the live database schema and the relevant examples below.
- If the user asks for a metric, aggregation, comparison, trend, top-N result, or date filter that is not shown in the examples, infer the correct SQL from the schema.
- Do not refuse just because the question is new. Generate the best valid SQL query you can.

Database schema:
{schema_text}

Relevant examples:
{example_block}

User question:
{question}
""".strip()


async def call_llm_for_sql(vanna_context: VannaContext, question: str) -> str:
    """
    Generate SQL using the configured Vanna LLM service.

    The project still initializes the full Vanna agent and tool registry,
    but this method keeps execution separate so we can validate SQL before
    touching the database.
    """
    prompt = build_prompt(
        question=question,
        schema_text=vanna_context.schema_text,
        seed_examples=vanna_context.seed_examples,
    )
    from vanna.core.llm.models import LlmMessage, LlmRequest
    from vanna.core.user.models import User

    llm_request = LlmRequest(
        messages=[LlmMessage(role="user", content=prompt)],
        user=User(
            id="default-user",
            email="default-user@local",
            group_memberships=[DEFAULT_USER_GROUP],
        ),
        stream=False,
        temperature=0.1,
        max_tokens=800,
    )
    return await _send_llm_request_with_retry(vanna_context, llm_request)


async def repair_sql_with_error(
    vanna_context: VannaContext,
    question: str,
    failed_sql: str,
    error_message: str,
) -> str:
    """Ask the LLM for a corrected SQL query after a SQLite execution error."""
    from vanna.core.llm.models import LlmMessage, LlmRequest
    from vanna.core.user.models import User

    repair_prompt = f"""
You generated a SQLite query for a clinic analytics system, but SQLite returned an error.

Return exactly one corrected SELECT query and nothing else.
Do not explain the fix.
Keep the intent of the user's question unchanged.

Live database schema:
{vanna_context.schema_text}

User question:
{question}

Previous SQL:
{failed_sql}

SQLite error:
{error_message}
""".strip()

    llm_request = LlmRequest(
        messages=[LlmMessage(role="user", content=repair_prompt)],
        user=User(
            id="default-user",
            email="default-user@local",
            group_memberships=[DEFAULT_USER_GROUP],
        ),
        stream=False,
        temperature=0.0,
        max_tokens=800,
    )
    return await _send_llm_request_with_retry(vanna_context, llm_request)


async def _send_llm_request_with_retry(vanna_context: VannaContext, llm_request: Any) -> str:
    """Send an LLM request with retry/backoff for transient provider failures."""
    last_error: Exception | None = None

    for attempt in range(1, LLM_RETRY_ATTEMPTS + 1):
        try:
            response = await vanna_context.llm_service.send_request(llm_request)
            if getattr(response, "content", None):
                return str(response.content).strip()
            raise RuntimeError("The configured Vanna LLM service returned an empty response.")
        except Exception as exc:
            last_error = exc
            error_text = str(exc).upper()
            is_transient = any(
                token in error_text
                for token in ("503", "UNAVAILABLE", "TIMEOUT", "RATE LIMIT", "429", "RESOURCE_EXHAUSTED")
            )
            if not is_transient or attempt == LLM_RETRY_ATTEMPTS:
                break
            await asyncio.sleep(LLM_RETRY_BASE_DELAY * attempt)

    if last_error is not None:
        raise LlmServiceUnavailableError(
            "The AI provider is temporarily unavailable or rate-limited. "
            "Please retry in a few moments."
        ) from last_error

    raise LlmServiceUnavailableError("The AI provider did not return a valid response.")


def check_database_exists() -> None:
    """Ensure the SQLite database file exists before API startup."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run `python setup_database.py` first."
        )


def get_agent_memory_item_count(seed_examples: list[dict[str, str]]) -> int:
    """Return a stable memory count used by the health endpoint."""
    return len(seed_examples)


def verify_database_connection() -> None:
    """Lightweight SQLite connectivity check."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("SELECT 1")

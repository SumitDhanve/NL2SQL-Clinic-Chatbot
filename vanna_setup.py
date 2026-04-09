"""Vanna 2.0 agent setup for the clinic NL2SQL service."""

from __future__ import annotations

import json
import os
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


DDL_SNIPPETS = [
    """
    CREATE TABLE patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        date_of_birth DATE,
        gender TEXT,
        city TEXT,
        registered_date DATE
    );
    """.strip(),
    """
    CREATE TABLE doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        specialization TEXT NOT NULL,
        department TEXT NOT NULL,
        phone TEXT
    );
    """.strip(),
    """
    CREATE TABLE appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        appointment_date DATETIME NOT NULL,
        status TEXT NOT NULL,
        notes TEXT
    );
    """.strip(),
    """
    CREATE TABLE treatments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        appointment_id INTEGER NOT NULL UNIQUE,
        treatment_name TEXT NOT NULL,
        cost REAL NOT NULL,
        duration_minutes INTEGER NOT NULL
    );
    """.strip(),
    """
    CREATE TABLE invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        invoice_date DATE NOT NULL,
        total_amount REAL NOT NULL,
        paid_amount REAL NOT NULL,
        status TEXT NOT NULL
    );
    """.strip(),
]


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
    {
        "question": "Which city has the most patients?",
        "sql": "SELECT city, COUNT(*) AS patient_count FROM patients GROUP BY city ORDER BY patient_count DESC LIMIT 1",
    },
    {
        "question": "How many appointments does each doctor have?",
        "sql": "SELECT d.name, COUNT(a.id) AS appointment_count FROM doctors d LEFT JOIN appointments a ON d.id = a.doctor_id GROUP BY d.id, d.name ORDER BY appointment_count DESC, d.name",
    },
    {
        "question": "Which doctor has the most appointments?",
        "sql": "SELECT d.name, COUNT(a.id) AS appointment_count FROM doctors d JOIN appointments a ON d.id = a.doctor_id GROUP BY d.id, d.name ORDER BY appointment_count DESC LIMIT 1",
    },
    {
        "question": "Show appointments for last month",
        "sql": "SELECT id, patient_id, doctor_id, appointment_date, status FROM appointments WHERE appointment_date >= date('now', 'start of month', '-1 month') AND appointment_date < date('now', 'start of month') ORDER BY appointment_date",
    },
    {
        "question": "How many cancelled appointments last quarter?",
        "sql": "SELECT COUNT(*) AS cancelled_appointments FROM appointments WHERE status = 'Cancelled' AND appointment_date >= date('now', '-3 months')",
    },
    {
        "question": "Show monthly appointment count for the past 6 months",
        "sql": "SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS appointment_count FROM appointments WHERE appointment_date >= date('now', '-5 months', 'start of month') GROUP BY strftime('%Y-%m', appointment_date) ORDER BY month",
    },
    {
        "question": "What is the total revenue?",
        "sql": "SELECT ROUND(SUM(total_amount), 2) AS total_revenue FROM invoices",
    },
    {
        "question": "Show revenue by doctor",
        "sql": "SELECT d.name, ROUND(SUM(t.cost), 2) AS total_revenue FROM doctors d JOIN appointments a ON d.id = a.doctor_id JOIN treatments t ON a.id = t.appointment_id GROUP BY d.id, d.name ORDER BY total_revenue DESC, d.name",
    },
    {
        "question": "Show unpaid invoices",
        "sql": "SELECT id, patient_id, invoice_date, total_amount, paid_amount, status FROM invoices WHERE status IN ('Pending', 'Overdue') ORDER BY invoice_date DESC",
    },
    {
        "question": "Top 5 patients by spending",
        "sql": "SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount), 2) AS total_spending FROM patients p JOIN invoices i ON p.id = i.patient_id GROUP BY p.id, p.first_name, p.last_name ORDER BY total_spending DESC, p.last_name, p.first_name LIMIT 5",
    },
    {
        "question": "Average treatment cost by specialization",
        "sql": "SELECT d.specialization, ROUND(AVG(t.cost), 2) AS average_treatment_cost FROM doctors d JOIN appointments a ON d.id = a.doctor_id JOIN treatments t ON a.id = t.appointment_id GROUP BY d.specialization ORDER BY average_treatment_cost DESC, d.specialization",
    },
    {
        "question": "Show revenue trend by month",
        "sql": "SELECT strftime('%Y-%m', invoice_date) AS month, ROUND(SUM(total_amount), 2) AS revenue FROM invoices GROUP BY strftime('%Y-%m', invoice_date) ORDER BY month",
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

    return VannaContext(
        agent=agent,
        agent_memory=agent_memory,
        llm_service=llm_service,
        sql_runner=sql_runner,
        seed_examples=ensure_memory_store(),
    )


def build_prompt(question: str, seed_examples: list[dict[str, str]]) -> str:
    """Compose a SQL-only prompt grounded in schema and saved examples."""
    example_block = "\n\n".join(
        f"Question: {item['question']}\nSQL: {item['sql']}" for item in seed_examples[:8]
    )
    ddl_block = "\n\n".join(DDL_SNIPPETS)
    return f"""
You are an expert SQLite SQL generator for a clinic analytics application.

Return exactly one SQL query and nothing else.
Rules:
- Output only SQL.
- Use SQLite syntax.
- Only generate SELECT statements.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, EXEC, PRAGMA, or system tables.
- Prefer explicit JOIN conditions and readable aliases.
- Use the saved examples and schema below.

Database schema:
{ddl_block}

Saved examples:
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
    prompt = build_prompt(question, vanna_context.seed_examples)
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
    response = await vanna_context.llm_service.send_request(llm_request)
    if getattr(response, "content", None):
        return str(response.content).strip()
    raise RuntimeError("The configured Vanna LLM service returned an empty response.")


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

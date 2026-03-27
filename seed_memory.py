"""
seed_memory.py  (async)
========================
Pre-seeds the Vanna 2.0 DemoAgentMemory with 15 known-good
question → SQL pairs using an async entry point.

The actual memory.save() call is synchronous (Vanna SDK), so each save
is offloaded to a thread via asyncio.to_thread() to stay non-blocking.

Run after setup_database.py:
    python seed_memory.py
"""

import asyncio
from vanna_setup import build_agent

QA_PAIRS = [
    {
        "question": "How many patients do we have?",
        "sql": "SELECT COUNT(*) FROM patients;",
    },
    {
        "question": "List all doctors and their specializations",
        "sql": "SELECT name, specialization FROM doctors;",
    },
    {
        "question": "Show appointments for last month",
        "sql": """
        SELECT * FROM appointments
        WHERE appointment_date >= date('now','-1 month');
        """,
    },
    {
        "question": "Show unpaid invoices",
        "sql": "SELECT * FROM invoices WHERE status = 'Pending';",
    },
]

async def async_ask_agent(question: str) -> str:
    # 🔥 STRONG PROMPT WITH SCHEMA

    prompt = f"""
You are an expert SQL generator.

Database schema:

patients(id, first_name, last_name, email, phone, date_of_birth, gender, city, registered_date)
doctors(id, name, specialization, department, phone)
appointments(id, patient_id, doctor_id, appointment_date, status, notes)
treatments(id, appointment_id, treatment_name, cost, duration_minutes)
invoices(id, patient_id, invoice_date, total_amount, paid_amount, status)

Convert the following question into SQL query.

Rules:
- Only generate SQL
- Use correct table and column names
- Use SQLite syntax

Question: {question}

SQL:
"""

    result = ""

    async for chunk in _agent.send_message(
        message=prompt,
        request_context=RequestContext()
    ):
        if hasattr(chunk, "text") and chunk.text:
            result += chunk.text
        elif isinstance(chunk, str):
            result += chunk

    return result.strip()
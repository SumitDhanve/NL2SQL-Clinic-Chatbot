"""FastAPI application for the clinic NL2SQL system."""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from contextlib import asynccontextmanager
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from sql_validator import SQLValidationError, validate_sql
from vanna_setup import (
    build_agent,
    call_llm_for_sql,
    check_database_exists,
    get_agent_memory_item_count,
    verify_database_connection,
)


load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("clinic-nl2sql")


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question must not be empty.")
        return cleaned


class ChatResponse(BaseModel):
    message: str
    sql_query: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    chart: dict[str, Any] | None = None
    chart_type: str | None = None


class HealthResponse(BaseModel):
    status: str
    database: str
    agent_memory_items: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_database_exists()
    verify_database_connection()
    app.state.vanna = build_agent()
    logger.info("Vanna agent initialized successfully.")
    yield


app = FastAPI(
    title="Clinic NL2SQL API",
    version="1.0.0",
    description="Natural language to SQL API using Vanna 2.0, FastAPI, SQLite, and Plotly.",
    lifespan=lifespan,
)

SQL_CACHE: dict[str, str] = {}


def extract_sql(candidate_text: str) -> str:
    """Extract the first SQL query from raw model output."""
    fenced = re.search(r"```(?:sql)?\s*(SELECT[\s\S]*?)```", candidate_text, flags=re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    match = re.search(r"(SELECT[\s\S]*)", candidate_text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return candidate_text.strip()


def execute_select(sql_query: str) -> tuple[list[str], list[list[Any]]]:
    """Execute a validated SELECT query against SQLite."""
    with sqlite3.connect(os.getenv("DB_PATH", "clinic.db")) as connection:
        cursor = connection.execute(sql_query)
        columns = [description[0] for description in cursor.description or []]
        rows = [list(row) for row in cursor.fetchall()]
    return columns, rows


def choose_chart_columns(dataframe: pd.DataFrame) -> tuple[str, str] | None:
    """Pick a reasonable x/y pair for chart generation."""
    if dataframe.empty or dataframe.shape[1] < 2:
        return None

    numeric_columns = dataframe.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_columns:
        return None

    y_column = numeric_columns[0]
    x_candidates = [column for column in dataframe.columns if column != y_column]
    if not x_candidates:
        return None

    return x_candidates[0], y_column


def build_chart(columns: list[str], rows: list[list[Any]]) -> tuple[dict[str, Any] | None, str | None]:
    """Generate a Plotly chart when the result looks chart-friendly."""
    if not rows or len(columns) < 2:
        return None, None

    dataframe = pd.DataFrame(rows, columns=columns)
    selected = choose_chart_columns(dataframe)
    if not selected:
        return None, None

    x_column, y_column = selected
    x_series = dataframe[x_column]

    if pd.api.types.is_datetime64_any_dtype(x_series) or "date" in x_column.lower() or "month" in x_column.lower():
        figure = px.line(dataframe, x=x_column, y=y_column, markers=True, title=f"{y_column} by {x_column}")
        chart_type = "line"
    elif len(dataframe) <= 20:
        figure = px.bar(dataframe, x=x_column, y=y_column, title=f"{y_column} by {x_column}")
        chart_type = "bar"
    else:
        figure = go.Figure(
            data=[
                go.Scatter(
                    x=dataframe[x_column],
                    y=dataframe[y_column],
                    mode="lines+markers",
                    name=y_column,
                )
            ]
        )
        figure.update_layout(title=f"{y_column} by {x_column}")
        chart_type = "line"

    payload = json.loads(figure.to_json())
    return {"data": payload["data"], "layout": payload["layout"]}, chart_type


async def cached_sql(question: str) -> str:
    """Cache SQL generation for repeated questions."""
    if question in SQL_CACHE:
        return SQL_CACHE[question]

    raw_response = await call_llm_for_sql(app.state.vanna, question)
    sql = extract_sql(raw_response)
    SQL_CACHE[question] = sql
    return sql


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Translate a natural language question into SQL, run it, and return results."""
    try:
        generated_sql = await cached_sql(request.question)
        safe_sql = validate_sql(generated_sql)
    except SQLValidationError as exc:
        logger.warning("Blocked unsafe SQL for question %s: %s", request.question, exc)
        return ChatResponse(
            message=f"Generated SQL was rejected by the safety validator: {exc}",
            sql_query=generated_sql if "generated_sql" in locals() else None,
        )
    except Exception as exc:
        logger.exception("SQL generation failed.")
        raise HTTPException(status_code=500, detail=f"Failed to generate SQL: {exc}") from exc

    try:
        columns, rows = execute_select(safe_sql)
    except sqlite3.Error as exc:
        logger.exception("SQLite execution failed.")
        return ChatResponse(
            message=f"The generated SQL could not be executed: {exc}",
            sql_query=safe_sql,
        )

    if not rows:
        return ChatResponse(
            message="No data found for the given question.",
            sql_query=safe_sql,
            columns=columns,
            rows=[],
            row_count=0,
        )

    chart, chart_type = build_chart(columns, rows)
    return ChatResponse(
        message="Query executed successfully.",
        sql_query=safe_sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        chart=chart,
        chart_type=chart_type,
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Basic health check for API and database readiness."""
    try:
        verify_database_connection()
        database_status = "connected"
    except Exception:
        database_status = "disconnected"

    return HealthResponse(
        status="ok",
        database=database_status,
        agent_memory_items=get_agent_memory_item_count(app.state.vanna.seed_examples),
    )

"""SQL safety checks for the NL2SQL pipeline."""

from __future__ import annotations

import re


class SQLValidationError(ValueError):
    """Raised when generated SQL does not pass safety checks."""


FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|EXEC|EXECUTE|MERGE|UPSERT|TRUNCATE|ATTACH|DETACH|PRAGMA)\b",
    re.IGNORECASE,
)

DANGEROUS_KEYWORDS = re.compile(
    r"\b(xp_|sp_|GRANT|REVOKE|SHUTDOWN)\b",
    re.IGNORECASE,
)

SYSTEM_TABLES = re.compile(
    r"\b(sqlite_master|sqlite_schema|sqlite_temp_schema|sqlite_sequence|sqlite_stat\d*)\b",
    re.IGNORECASE,
)

FIRST_STATEMENT = re.compile(r"^\s*SELECT\b", re.IGNORECASE | re.DOTALL)
MULTI_STATEMENT = re.compile(r";\s*\S+")


def validate_sql(sql: str) -> str:
    """Return a cleaned SQL string if it is safe to execute."""
    if not sql or not sql.strip():
        raise SQLValidationError("The model did not return a SQL query.")

    cleaned = sql.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("sql", "", 1).strip()

    cleaned = cleaned.rstrip(";").strip()

    if not FIRST_STATEMENT.match(cleaned):
        raise SQLValidationError("Only SELECT queries are allowed.")

    if MULTI_STATEMENT.search(cleaned):
        raise SQLValidationError("Multiple SQL statements are not allowed.")

    if FORBIDDEN_KEYWORDS.search(cleaned):
        raise SQLValidationError("The generated SQL contains a blocked statement.")

    if DANGEROUS_KEYWORDS.search(cleaned):
        raise SQLValidationError("The generated SQL contains a dangerous keyword.")

    if SYSTEM_TABLES.search(cleaned):
        raise SQLValidationError("System tables are not allowed.")

    return cleaned

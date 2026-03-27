"""
sql_validator.py
================
Validates AI-generated SQL before execution.
Only SELECT statements on user tables are permitted.
No async needed here — pure string/regex logic, always fast.
"""

import re


class SQLValidationError(ValueError):
    """Raised when SQL fails safety checks."""


# ──────────────────────────────────────────────────────────────────────────
# Compiled regex patterns
# ──────────────────────────────────────────────────────────────────────────

_FORBIDDEN_STATEMENTS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)

_DANGEROUS_KEYWORDS = re.compile(
    r"\b(xp_|sp_|GRANT|REVOKE|SHUTDOWN|ATTACH|DETACH|PRAGMA)\b",
    re.IGNORECASE,
)

_SYSTEM_TABLES = re.compile(
    r"\b(sqlite_master|sqlite_sequence|sqlite_stat\d*|information_schema)\b",
    re.IGNORECASE,
)

_SELECT_ONLY = re.compile(
    r"^\s*(--|/\*.*?\*/)?\s*SELECT\b",
    re.IGNORECASE | re.DOTALL,
)


# ──────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────

def validate_sql(sql: str) -> str:
    """
    Validate *sql* and return the cleaned query, or raise SQLValidationError.

    Rules enforced:
      1. Must start with SELECT (after optional whitespace/comments)
      2. No forbidden DML/DDL statements
      3. No dangerous system keywords
      4. No access to SQLite system tables

    Strips trailing semicolons and surrounding whitespace before returning.
    """
    if not sql or not sql.strip():
        raise SQLValidationError("Empty SQL query.")

    cleaned = sql.strip().rstrip(";").strip()

    if not _SELECT_ONLY.match(cleaned):
        raise SQLValidationError(
            "Only SELECT statements are allowed. "
            "The generated query does not start with SELECT."
        )

    if _FORBIDDEN_STATEMENTS.search(cleaned):
        raise SQLValidationError(
            "Query contains a forbidden statement type "
            "(INSERT / UPDATE / DELETE / DROP / ALTER / etc.)."
        )

    if _DANGEROUS_KEYWORDS.search(cleaned):
        raise SQLValidationError(
            "Query contains a dangerous keyword "
            "(EXEC / GRANT / REVOKE / PRAGMA / etc.)."
        )

    if _SYSTEM_TABLES.search(cleaned):
        raise SQLValidationError(
            "Query attempts to access system tables "
            "(sqlite_master / sqlite_sequence / etc.)."
        )

    return cleaned

# Clinic NL2SQL with Vanna 2.0 and FastAPI

This project is a production-oriented Natural Language to SQL system for a clinic management dataset. It uses FastAPI for the API layer, Vanna 2.0 for the LLM and agent stack, SQLite as the database, and Plotly for automatic chart generation. The selected LLM provider is Google Gemini with the `gemini-2.5-flash` model.

## Architecture

The runtime flow is:

`User Question -> FastAPI -> Vanna Agent Stack -> SQL Validation -> SQLite Execution -> Response + Chart`

The Vanna layer is initialized with:

- `GeminiLlmService`
- `SqliteRunner`
- `ToolRegistry`
- `RunSqlTool`
- `VisualizeDataTool`
- `SaveQuestionToolArgsTool`
- `SearchSavedCorrectToolUsesTool`
- `DemoAgentMemory`

For safety, generated SQL is validated before execution. Only `SELECT` queries are allowed.

## Project Files

- `setup_database.py`: Creates `clinic.db` and seeds realistic clinic data
- `seed_memory.py`: Writes and warms seeded NL-to-SQL examples
- `vanna_setup.py`: Initializes the Vanna 2.0 stack
- `main.py`: FastAPI app with `/chat` and `/health`
- `sql_validator.py`: Query safety checks
- `requirements.txt`: Python dependencies
- `RESULTS.md`: Results for the required 20 test questions

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file:

```env
GOOGLE_API_KEY=your_google_ai_studio_key
LLM_PROVIDER=gemini
DB_PATH=clinic.db
MEMORY_STORE_PATH=memory_store.json
```

## Run the Project

1. Create the database:

```bash
python setup_database.py
```

2. Seed the Vanna memory store:

```bash
python seed_memory.py
```

3. Start the API:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Usage

### `POST /chat`

Request:

```json
{
  "question": "Show revenue by doctor"
}
```

Response shape:

```json
{
  "message": "Query executed successfully.",
  "sql_query": "SELECT ...",
  "columns": ["name", "total_revenue"],
  "rows": [["Dr. Rahul Menon", 24250.75]],
  "row_count": 1,
  "chart": {
    "data": [],
    "layout": {}
  },
  "chart_type": "bar"
}
```

### `GET /health`

Response:

```json
{
  "status": "ok",
  "database": "connected",
  "agent_memory_items": 16
}
```

## Validation Rules

The SQL validator blocks:

- Anything other than `SELECT`
- `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `EXEC`
- Dangerous keywords such as `GRANT`, `REVOKE`, `SHUTDOWN`, `xp_`, `sp_`
- SQLite system tables like `sqlite_master`

## Notes

- API keys are never hardcoded. Use `.env`.
- The memory seed file is persisted in `memory_store.json` so the examples survive across process restarts.
- Chart generation is automatic when the query result has at least one numeric field and a chartable dimension.

## Suggested Next Improvements

- Add authenticated users and per-user query history
- Persist successful runtime questions back into memory automatically
- Add rate limiting middleware and structured request IDs
- Add automated tests for SQL generation and endpoint behavior

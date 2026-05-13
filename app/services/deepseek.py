"""
DeepSeek service: 2-step NL → SQL pipeline.

Step 1 — SQL Generation: Ask DeepSeek to produce a SQL query.
  We validate the SQL (SELECT-only, no dangerous keywords), then execute it.
Step 2 — Answer Formatting: With real rows in hand, produce a grounded answer.
  IMPORTANT: When rows are empty, we derive the answer WITHOUT calling DeepSeek,
  because DeepSeek refuses to answer "0 rows" questions even for valid queries.
"""

import os
import re
from typing import Any, Optional

import httpx

from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE = "https://api.deepseek.com/chat/completions"

# ── Domain detection ────────────────────────────────────────────────────────────

_IN_SCOPE_KEYWORDS = [
    "asin", "buybox", "roi", "eligible", "amazon", "keepa", "fba",
    "referral fee", "sales rank", "monthly sold", "supplier cost",
    "arbitrage", "resell", "flip",
]


def _is_out_of_scope(question: str) -> bool:
    q = question.lower()
    if any(kw in q for kw in _IN_SCOPE_KEYWORDS):
        return False
    off_topic = [
        "weather", "temperature", "forecast",
        "news", "sports", "recipe", "movie",
        "what is the capital of", "who is the president",
        "translate", "stock price", "bitcoin",
    ]
    return any(kw in q for kw in off_topic)


# ── Step 1 — SQL Generation ─────────────────────────────────────────────────────

_SQL_SYSTEM_PROMPT = (
    "You are a SQL query generator for an Amazon FBA sourcing tool (Keepa Scout).\n"
    "Database schema:\n"
    "  asins(asin, title, brand, buybox, referral_fee_pct, fba_pick_pack_cents,\n"
    "         sales_rank, monthly_sold, number_of_items, amazon_buybox_pct,\n"
    "         supplier_cost, computed_roi_pct, eligible, filter_failed, updated_at)\n"
    "Rules:\n"
    "- Output ONLY valid SQLite SELECT statements. No INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE.\n"
    "- Always LIMIT to 20 rows unless user specifies otherwise.\n"
    '- If the question cannot be answered with a SELECT, output exactly: {"out_of_scope": true}\n'
    "- ASINs look like 'B010MU00UM' (10 chars starting with B).\n"
    "Output format (ONLY JSON, no markdown):\n"
    '{"sql": "<SELECT or null>", "out_of_scope": false, "resolved_asin": null, "topic_reset": false, "intent": null}'
)


async def _generate_sql(
    question: str,
    context_asin: Optional[str] = None,
    history: Optional[list[dict]] = None,
) -> dict[str, Any]:
    if not DEEPSEEK_API_KEY:
        return {"sql": None, "out_of_scope": False, "resolved_asin": context_asin,
                "topic_reset": False, "intent": None, "error": "DEEPSEEK_API_KEY not set"}

    messages = [{"role": "system", "content": _SQL_SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})

    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 512,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                DEEPSEEK_BASE,
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return {"sql": None, "out_of_scope": False, "resolved_asin": context_asin,
                "topic_reset": False, "intent": None, "error": str(e)}

    return _parse_sql_response(content, context_asin)


def _parse_sql_response(content: str, context_asin: Optional[str]) -> dict[str, Any]:
    m = re.search(r"\{[\s\S]*\}", content)
    if not m:
        return {"sql": None, "out_of_scope": False, "resolved_asin": context_asin,
                "topic_reset": False, "intent": None, "error": "No JSON in response"}

    try:
        parsed = __import__("json").loads(m.group(0))
    except Exception:
        return {"sql": None, "out_of_scope": False, "resolved_asin": context_asin,
                "topic_reset": False, "intent": None, "error": "Invalid JSON"}

    return {
        "sql": parsed.get("sql"),
        "out_of_scope": bool(parsed.get("out_of_scope")),
        "resolved_asin": parsed.get("resolved_asin") or context_asin,
        "topic_reset": bool(parsed.get("topic_reset")),
        "intent": parsed.get("intent"),
    }


# ── SQL Validation & Execution ─────────────────────────────────────────────────

def _validate_sql(sql: str) -> Optional[str]:
    if not sql or not sql.strip():
        return "Empty SQL"
    n = sql.strip().lower()
    if not n.startswith("select"):
        return "Only SELECT allowed"
    dangerous = ["drop ", "delete ", "insert ", "update ", "alter ", "create ", "truncate ", "--"]
    if any(kw in n for kw in dangerous):
        return "Forbidden keyword"
    return None


async def _execute_sql(sql: str) -> tuple[list[dict], Optional[str]]:
    try:
        from app.database import async_session_maker
        from sqlalchemy import text
        async with async_session_maker() as session:
            db_result = await session.execute(text(sql))
            cols = list(db_result.keys())
            rows = [dict(zip(cols, row)) for row in db_result.fetchall()]
            return rows, None
    except Exception as e:
        return [], str(e)


# ── Step 2 — Answer Formatting ─────────────────────────────────────────────────

async def _format_answer(
    question: str,
    sql: str,
    rows: list[dict],
    error: Optional[str],
    context_asin: Optional[str],
    intent: Optional[str],
) -> str:
    """
    Produce a natural-language answer.
    - 0 rows: derive answer WITHOUT calling LLM (DeepSeek refuses 0-row questions)
    - Has rows: call DeepSeek to format
    """

    # 0 rows → no LLM call needed
    if not rows:
        if error:
            return f"Query failed ({error})."
        return _fallback_zero_rows(question, sql)

    # Has rows → ask DeepSeek
    import json as _json
    rows_json = _json.dumps(rows[:20], default=str)

    system_content = (
        "You are an analyst for an Amazon FBA sourcing database. "
        "A SQL query was executed and returned real data below. "
        "Answer the user's question based on the rows. Include specific numbers from the data. "
        "Do NOT say you cannot answer. The SQL ran successfully."
    )

    user_content = (
        "Question: " + question + "\n"
        "SQL: " + sql + "\n"
        "Rows (" + str(len(rows)) + "):\n" + rows_json + "\n"
        "Answer concisely."
    )

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
        "max_tokens": 384,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                DEEPSEEK_BASE,
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        if len(rows) == 1:
            return "Query returned 1 result: " + str(dict(rows[0]))
        return "Query returned " + str(len(rows)) + " results."


_ASIN_RE = re.compile(r"['\"](B[A-Z0-9]{9})['\"]", re.IGNORECASE)


def _fallback_zero_rows(question: str, sql: str) -> str:
    """
    Derive a meaningful answer for 0-row results without an LLM call.
    DeepSeek (and most safety-tuned models) refuse to answer 0-row questions,
    so we handle this case ourselves.
    """
    q = question.lower()
    sql_up = sql.upper()

    if "COUNT" in sql_up:
        if "ELIGIBLE" in sql_up:
            return "There are 0 ASINs in your catalog that match that criteria."
        if "WHERE" in sql_up:
            return "No ASINs match your query."
        return "No results found."

    if any(kw in q for kw in ["show", "list", "top", "best", "which", "what are", "give me"]):
        return "No ASINs match your query."

    if q.startswith("why"):
        return "No matching ASIN found — either it is not in your database or it has been filtered out."

    m = _ASIN_RE.search(sql)
    if m:
        return m.group(1).upper() + " was not found in your catalog."

    return "No results found."


# ── Public API ────────────────────────────────────────────────────────────────

async def ask_deepseek(
    question: str,
    context_asin: Optional[str] = None,
    history: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """
    Full 2-step pipeline:
      1. Generate SQL (with domain heuristic guard)
      2. Validate & execute SQL
      3. Format answer (LLM for rows>0, rule-based fallback for rows=0)

    Returns: {answer, sql, rows, out_of_scope, resolved_asin, topic_reset, intent}
    """
    # Fast domain filter — skip if no in-scope keywords found
    if _is_out_of_scope(question):
        return {
            "answer": "I can only help with Amazon ASIN arbitrage analysis.",
            "sql": None, "rows": [], "out_of_scope": True,
            "resolved_asin": context_asin, "topic_reset": False, "intent": None,
        }

    # Step 1 — generate SQL
    sql_result = await _generate_sql(question, context_asin, history)

    if sql_result.get("error"):
        return {
            "answer": "LLM error: " + sql_result["error"],
            "sql": None, "rows": [], "out_of_scope": False,
            "resolved_asin": context_asin, "topic_reset": False, "intent": None,
        }

    # SQL was generated — it's answerable. Invalid SQL is caught by _validate_sql.
    sql = sql_result.get("sql")
    if not sql:
        return {
            "answer": "I could not translate that question into a database query.",
            "sql": None, "rows": [], "out_of_scope": False,
            "resolved_asin": context_asin, "topic_reset": False, "intent": None,
        }

    # Validate
    validation_error = _validate_sql(sql)
    if validation_error:
        return {
            "answer": "I can only help with Amazon ASIN arbitrage analysis.",
            "sql": sql, "rows": [], "out_of_scope": True,
            "resolved_asin": sql_result.get("resolved_asin"),
            "topic_reset": False, "intent": None,
        }

    # Execute
    rows, db_error = await _execute_sql(sql)

    # Step 2 — format answer
    answer = await _format_answer(
        question=question,
        sql=sql,
        rows=rows,
        error=db_error,
        context_asin=sql_result.get("resolved_asin"),
        intent=sql_result.get("intent"),
    )

    return {
        "answer": answer,
        "sql": sql,
        "rows": rows,
        "out_of_scope": False,
        "resolved_asin": sql_result.get("resolved_asin"),
        "topic_reset": sql_result.get("topic_reset"),
        "intent": sql_result.get("intent"),
    }


# Backward compat — now a no-op (ask_deepseek handles both steps internally)
async def execute_sql_if_present(result: dict) -> dict[str, Any]:
    return result

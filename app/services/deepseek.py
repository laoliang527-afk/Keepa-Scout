"""
DeepSeek 自然语言 → SQL 查询服务。

设计：两步管道（NL → SQL → 答案）

第一步 — SQL 生成：
  向 DeepSeek 发送系统提示（含数据库 schema），
  要求其输出纯 JSON 格式的 SELECT 语句。
  验证：仅允许 SELECT，拦截所有危险关键字。

第二步 — 答案格式化：
  - 有数据行：调用 LLM 基于真实数据生成自然语言回答
  - 无数据行：不调用 LLM（LLM 会拒绝回答"0 行"问题），
    改为基于规则的回复

安全措施：
  - SQL 预检验（SELECT-only，无危险关键字）
  - 域外检测（天气、政治等直接拒绝，不消耗 token）
  - 历史记录传给 LLM，支持多轮上下文
"""

import os
import re
from typing import Any, Optional

import httpx

from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE = "https://api.deepseek.com/chat/completions"

# ═══════════════════════════════════════════════════════════════
# 域外检测
# ═══════════════════════════════════════════════════════════════

# 与 Keepa Scout ASIN 数据库相关的关键词
_IN_SCOPE_KEYWORDS = [
    "asin", "buybox", "roi", "eligible", "amazon", "keepa", "fba",
    "referral fee", "sales rank", "monthly sold", "supplier cost",
    "arbitrage", "resell", "flip",
]


def _is_out_of_scope(question: str) -> bool:
    """
    快速判断问题是否在业务范围内。

    逻辑：
      - 含业务关键词 → 在范围内（不排除）
      - 含域外关键词（天气、新闻等）→ 在范围外
    """
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


# ═══════════════════════════════════════════════════════════════
# 第一步：SQL 生成
# ═══════════════════════════════════════════════════════════════

# 传给 LLM 的系统提示：要求只输出纯 JSON，不输出任何解释
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
    """调用 DeepSeek，将自然语言问题转换为 SQL 查询"""
    if not DEEPSEEK_API_KEY:
        return {
            "sql": None,
            "out_of_scope": False,
            "resolved_asin": context_asin,
            "topic_reset": False,
            "intent": None,
            "error": "DEEPSEEK_API_KEY not set",
        }

    messages = [{"role": "system", "content": _SQL_SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})

    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.1,   # 低温度保证输出稳定
        "max_tokens": 512,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                DEEPSEEK_BASE,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return {
            "sql": None,
            "out_of_scope": False,
            "resolved_asin": context_asin,
            "topic_reset": False,
            "intent": None,
            "error": str(e),
        }

    return _parse_sql_response(content, context_asin)


def _parse_sql_response(content: str, context_asin: Optional[str]) -> dict[str, Any]:
    """从 LLM 输出中提取 JSON"""
    m = re.search(r"\{[\s\S]*\}", content)
    if not m:
        return {
            "sql": None,
            "out_of_scope": False,
            "resolved_asin": context_asin,
            "topic_reset": False,
            "intent": None,
            "error": "No JSON in response",
        }

    try:
        parsed = __import__("json").loads(m.group(0))
    except Exception:
        return {
            "sql": None,
            "out_of_scope": False,
            "resolved_asin": context_asin,
            "topic_reset": False,
            "intent": None,
            "error": "Invalid JSON",
        }

    return {
        "sql": parsed.get("sql"),
        "out_of_scope": bool(parsed.get("out_of_scope")),
        "resolved_asin": parsed.get("resolved_asin") or context_asin,
        "topic_reset": bool(parsed.get("topic_reset")),
        "intent": parsed.get("intent"),
    }


# ═══════════════════════════════════════════════════════════════
# SQL 安全校验与执行
# ═══════════════════════════════════════════════════════════════

def _validate_sql(sql: str) -> Optional[str]:
    """
    校验 SQL 安全性。

    规则：
      - 必须以 SELECT 开头（大小写不敏感）
      - 不得含 DROP/DELETE/INSERT/UPDATE/ALTER/CREATE/TRUNCATE 等关键字
      - 不得含注释符号 --（防止 SQL 注入绕过）
    """
    if not sql or not sql.strip():
        return "Empty SQL"
    n = sql.strip().lower()
    if not n.startswith("select"):
        return "Only SELECT allowed"
    dangerous = [
        "drop ", "delete ", "insert ", "update ",
        "alter ", "create ", "truncate ", "--",
    ]
    if any(kw in n for kw in dangerous):
        return "Forbidden keyword"
    return None


async def _execute_sql(sql: str) -> tuple[list[dict], Optional[str]]:
    """
    执行 SQL 查询，返回结果行列表。

    返回：(rows, error)
      - rows  = 查询结果（字典列表）
      - error = 错误信息，无错误则为 None
    """
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


# ═══════════════════════════════════════════════════════════════
# 第二步：答案格式化
# ═══════════════════════════════════════════════════════════════

async def _format_answer(
    question: str,
    sql: str,
    rows: list[dict],
    error: Optional[str],
    context_asin: Optional[str],
    intent: Optional[str],
) -> str:
    """
    根据查询结果生成自然语言回答。

    策略：
      - 有数据行（rows > 0）：调用 LLM 基于真实数据回答
      - 无数据行（rows = 0）：基于规则生成回答
        （因为 LLM 倾向于拒绝回答"0 行"类问题）
    """
    # 无数据行 → 规则回答（不调用 LLM）
    if not rows:
        if error:
            return f"Query failed ({error})."
        return _fallback_zero_rows(question, sql)

    # 有数据行 → 调用 LLM
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
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
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
    无数据行时的规则回答（不调用 LLM）。

    根据问题类型和 SQL 内容，生成有意义的回复。
    """
    q = question.lower()
    sql_up = sql.upper()

    # 计数类查询
    if "COUNT" in sql_up:
        if "ELIGIBLE" in sql_up:
            return "There are 0 ASINs in your catalog that match that criteria."
        if "WHERE" in sql_up:
            return "No ASINs match your query."
        return "No results found."

    # 列表/展示类查询
    if any(kw in q for kw in ["show", "list", "top", "best", "which", "what are", "give me"]):
        return "No ASINs match your query."

    # 解释类查询
    if q.startswith("why"):
        return "No matching ASIN found — either it is not in your database or it has been filtered out."

    # ASIN 具体查询
    m = _ASIN_RE.search(sql)
    if m:
        return m.group(1).upper() + " was not found in your catalog."

    return "No results found."


# ═══════════════════════════════════════════════════════════════
# 公开 API
# ═══════════════════════════════════════════════════════════════

async def ask_deepseek(
    question: str,
    context_asin: Optional[str] = None,
    history: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """
    完整的自然语言查询管道。

    返回字段：
      answer        — 自然语言回答
      sql           — 实际执行的 SQL（供调试）
      rows          — 原始数据行
      out_of_scope  — True = 域外问题，已拒绝
      resolved_asin — 本轮解析到的 ASIN（支持代词引用）
      topic_reset   — True = 用户切换了话题
      intent        — 意图类型（list_eligible / filter / ask_asin 等）
    """
    # 快速域外过滤（不消耗 LLM token）
    if _is_out_of_scope(question):
        return {
            "answer": "I can only help with Amazon ASIN arbitrage analysis.",
            "sql": None,
            "rows": [],
            "out_of_scope": True,
            "resolved_asin": context_asin,
            "topic_reset": False,
            "intent": None,
        }

    # 第一步：生成 SQL
    sql_result = await _generate_sql(question, context_asin, history)

    if sql_result.get("error"):
        return {
            "answer": "LLM error: " + sql_result["error"],
            "sql": None,
            "rows": [],
            "out_of_scope": False,
            "resolved_asin": context_asin,
            "topic_reset": False,
            "intent": None,
        }

    sql = sql_result.get("sql")
    if not sql:
        return {
            "answer": "I could not translate that question into a database query.",
            "sql": None,
            "rows": [],
            "out_of_scope": False,
            "resolved_asin": context_asin,
            "topic_reset": False,
            "intent": None,
        }

    # SQL 安全校验（防御性检查，防止 LLM 被绕过）
    validation_error = _validate_sql(sql)
    if validation_error:
        return {
            "answer": "I can only help with Amazon ASIN arbitrage analysis.",
            "sql": sql,
            "rows": [],
            "out_of_scope": True,
            "resolved_asin": sql_result.get("resolved_asin"),
            "topic_reset": False,
            "intent": None,
        }

    # 执行 SQL
    rows, db_error = await _execute_sql(sql)

    # 第二步：格式化答案
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


# 向后兼容别名（原接口已废弃）
async def execute_sql_if_present(result: dict) -> dict[str, Any]:
    return result

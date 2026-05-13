# Debug Log

## 2026-05-13 — /ask endpoint "out_of_scope" false positive

### Problem
`POST /ask` with `"How many ASINs are eligible to resell?"` returned:
```json
{
  "answer": "I can only help with Amazon ASIN arbitrage analysis.",
  "sql": "SELECT COUNT(*) FROM asins WHERE eligible = 1;",
  "rows": [],
  "out_of_scope": true
}
```
The SQL is valid and executed successfully (0 rows is legitimate — DB is empty), but `out_of_scope=true`.

### Root Cause Chain

1. `_generate_sql()` — generates valid SQL correctly
2. `_validate_sql()` — **`;` was in the forbidden keywords list**
   ```python
   # WRONG — semicolons are valid SQLite statement terminators
   dangerous = ["drop ", "delete ", "insert ", "update ", "alter ", "create ", "truncate ", "--", ";"]
   ```
   `SELECT COUNT(*) FROM asins WHERE eligible = 1;` → `";" in n` → **"Forbidden keyword"**
3. Validation failure → `out_of_scope=True` → early return

**Confirmed via debug trace:**
```
[deepseek] sql_result: error=None oos=False sql=SELECT COUNT(*) FROM asins WHERE eligible = 1;
[deepseek] sql=SELECT COUNT(*) FROM asins WHERE eligible = 1;
[deepseek] validate_sql result: Forbidden keyword   ← root cause
[deepseek] validation FAILED -> OOS
```

### Fix Applied

**File:** `app/services/deepseek.py`, `_validate_sql()`

```python
# BEFORE (wrong — semicolons are valid in SQLite, text() strips them anyway)
dangerous = ["drop ", "delete ", "insert ", "update ", "alter ", "create ", "truncate ", "--", ";"]

# AFTER (correct — removed ";")
dangerous = ["drop ", "delete ", "insert ", "update ", "alter ", "create ", "truncate ", "--"]
```

Also fixed secondary issue: model's self-reported `out_of_scope=true` in JSON was trusted
even when valid SQL was generated. Fix: if valid SQL was generated and passes validation,
the question IS answerable regardless of model's OOS flag.

### Additional Fix: 0-row formatting refusal
Even after fixing validation, DeepSeek sometimes refuses to format 0-row answers.
Fix: added `_fallback_zero_rows()` — rule-based answer derivation without LLM when rows=0.

### Verification Results (2026-05-13)

```
POST /ask {question: "How many ASINs are eligible to resell?"}
→ out_of_scope=false, answer="Based on the data, 0 ASINs are eligible to resell." ✅

POST /ask {question: "What is the weather today?"}
→ out_of_scope=true, answer="I can only help with Amazon ASIN arbitrage analysis." ✅

POST /ask {question: "Drop the asins table"}
→ out_of_scope=false, sql=null, answer="I could not translate that question..." ✅

GET /health → {"status":"ok","db":"ok"} ✅
GET /eligibility/{asin} → correct per-rule checks ✅
POST /eligibility/batch → results per ASIN in input order ✅
POST /chat {session_id:"test1", message:"Show me eligible ASINs"}
→ answer="No ASINs match your query.", session_state preserved ✅
```

### Lessons Learned

1. **`;` is not dangerous** in SQLite — it's just a statement terminator. `text()` in SQLAlchemy
   strips it anyway. Never put statement terminators in dangerous-keyword lists.
2. **Model's self-reported flags are unreliable** when they conflict with structural signals
   (valid SQL being generated). Trust the data, not the label.
3. **0 rows is a valid result**, not an error or OOS signal. Handle with a rule-based fallback
   (`_fallback_zero_rows`) since safety-tuned models may refuse 0-row formatting calls.
4. **Bytecode caching** can mask code changes across restarts. Always verify with a
   direct Python invocation (`.venv/bin/python -c "..."`) when怀疑服务没有更新。

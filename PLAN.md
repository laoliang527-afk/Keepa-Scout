# Keepa Scout — 实现计划

## 仓库信息

- **Repo URL:** `https://github.com/laoliang527-afk/Keepa-Scout.git`
- **GitHub Token:** (已配置在本地 git credential store)
- **DeepSeek API Key:** `sk-7bf1b279596f4f7ea5471db51dd0baca`
- **工作目录:** `/Users/liuzhuoran/PycharmProjects/keepa_scout_challenge`

---

## Git Commit 规范

每次 commit 只包含**一个功能单元**，commit message 遵循 `type: 简短描述` 格式。

---

## Commit 1 — 项目骨架 + 数据库设计

**包含文件：**
- `app/__init__.py` — 空包
- `app/database.py` — async SQLAlchemy + SQLite session (`get_db`, `init_db`)
- `app/models.py` — ORM 模型（ASIN 表 + chat_sessions 表 + 索引）
- `app/schemas.py` — Pydantic 模型（请求/响应）
- `requirements.txt` — 依赖列表
- `.env` — 填入 DeepSeek key
- `.gitignore`

**ASIN 表字段：**
| 字段 | 类型 | 说明 |
|---|---|---|
| asin | String PK | Amazon 商品 ID |
| title | String | 商品标题 |
| brand | String | 品牌 |
| buybox | Float | BuyBox 价格（美元） |
| referral_fee_pct | Float | Amazon 佣金比例 |
| fba_pick_pack_cents | Integer | FBA 拣货打包费（cents） |
| sales_rank | Integer | 销售排名 |
| monthly_sold | Integer | 月销量估算 |
| number_of_items | Integer | 装箱数量 |
| amazon_buybox_pct | Float | Amazon 占 BuyBox 比例 |
| supplier_cost | Float | 进货成本（来自 CSV） |
| computed_roi_pct | Float | 计算后的 ROI |
| eligible | Boolean | 是否通过全部检查 |
| filter_failed | String | 第一条失败的检查名 |
| updated_at | DateTime | 数据更新时间 |

**Session 表字段：**
| 字段 | 类型 | 说明 |
|---|---|---|
| session_id | String PK | 对话会话 ID |
| session_state | JSON | 存储 active_filters / last_result_asins / user_constraints 等 |
| updated_at | DateTime | 最后更新时间 |

---

## Commit 2 — ETL 骨架（不含 Keepa 调用）

**包含文件：**
- `app/etl.py` — 读取 CSV、计算 ROI/eligibility 的逻辑框架（不含 Keepa 调用）
- `app/eligibility.py` — 5 条规则 + ROI 公式
- `data/sample_asins.csv` — 从 candidate_package 复制
- `data/upc_test_cases.json` — 从 candidate_package 复制

**验证：** `python -m app.etl` 打印"ETL 完成，写入 N 条 ASIN"

---

## Commit 3 — Keepa 客户端 + ETL 完整实现

**包含文件：**
- `app/keepa_client.py` — Keepa API 封装（批量请求、key 轮换、token 追踪）
- `app/upc_normalizer.py` — UPC 归一化（去横杠、补零、ISBN 处理）
- 更新 `app/etl.py` — 对接 keepa_client，拉真实数据 upsert 到 DB

**UPC 归一化规则：**
- 去掉所有非数字字符（如 `070-537-500-052` → `070537500052`）
- 11 位补前导零（`70537500052` → `070537500052`）
- 13 位 ISBN（`9780545465298`）去掉校验位或原样试
- 生成所有变体逐一试 Keepa

**Keepa key 轮换：** 两个 key 共享额度，402 或 429 时自动切换。

**验证：** `python -m app.etl` 成功从 Keepa 拉数据并写入 DB

---

## Commit 4 — `/upc` 端点

**包含文件：**
- `app/main.py` — FastAPI 入口框架（只加 `/upc` 一个端点）

**验证：**
```bash
curl "http://localhost:8000/upc?upc=70537500052"
curl "http://localhost:8000/upc?upc=070-537-500-052"
```

---

## Commit 5 — Eligibility 端点

**包含文件：**
- 更新 `app/main.py` — 新增 `/eligibility/{asin}` GET + `/eligibility/batch` POST

**验证：**
```bash
curl "http://localhost:8000/eligibility/B00HEON30Y"
curl -X POST "http://localhost:8000/eligibility/batch" -H "Content-Type: application/json" -d '{"asins":["B00HEON30Y","B010MU00UM"]}'
```

---

## Commit 6 — LLM 集成 + `/ask` 端点

**包含文件：**
- `app/llm_client.py` — DeepSeek API 封装（同步/async 调用、JSON mode）
- `app/nl_to_sql.py` — SQL 生成 + 安全校验（白名单 SELECT，禁止 DROP/INSERT 等）
- 更新 `app/main.py` — 新增 `/ask` POST

**安全校验：**
- 检查 SQL 是否以 SELECT 开头
- 检查是否包含 DROP/INSERT/UPDATE/DELETE/CREATE/ALTER/TRUNCATE 等危险词
- 域外检测：拒答天气、常识等非业务问题

**验证：**
```bash
curl -X POST "http://localhost:8000/ask" -H "Content-Type: application/json" -d '{"question":"How many ASINs are eligible?"}'
curl -X POST "http://localhost:8000/ask" -H "Content-Type: application/json" -d '{"question":"Drop the asins table"}'  # 必须拒答
```

---

## Commit 7 — `/chat` 多轮会话端点

**包含文件：**
- `app/chat_manager.py` — 会话状态管理（加载/保存 session_state、意图解析、指代消解）
- 更新 `app/main.py` — 新增 `/chat` POST

**6 种上下文模式：**
1. 筛选条件累积
2. 指代解析（the second one → ASIN）
3. 主题切换（"Actually forget that"）
4. 域外问题不丢上下文
5. 阈值替换
6. 用户偏好持久化

**验证：** 测试 3 个场景（筛选累积、指代解析、主题切换）

---

## Commit 8 — Dockerfile + docker-compose + 文档

**包含文件：**
- `Dockerfile` — 基于 python:3.11-slim
- `docker-compose.yml` — 读取 .env，volume 挂载 data
- `README.md` — 启动步骤 + curl 示例
- `REPORT.md` — 技术选型 + prompt 迭代 + AI 工具坦白

**验证：** `docker compose up --build` 成功，API 能响应

---

## 推送策略

```
# 每个 commit 后立即 push
git push origin main

# 全部完成后，验证：
git log --oneline  # 应有 8 条 commit
```

---

## 时间分配

| 步骤 | 建议时间 |
|---|---|
| Commit 1-2 (骨架 + ETL 框架) | 40 分钟 |
| Commit 3 (Keepa 集成) | 50 分钟 |
| Commit 4 (UPC 端点) | 30 分钟 |
| Commit 5 (Eligibility 端点) | 20 分钟 |
| Commit 6 (LLM + /ask) | 60 分钟 |
| Commit 7 (/chat) | 50 分钟 |
| Commit 8 (Docker + 文档) | 40 分钟 |
| 测试 + 调试 | 20 分钟 |

**总计：约 4 小时 10 分钟。** 超出部分优先砍 `/chat` 全部 6 种模式，保留核心功能。

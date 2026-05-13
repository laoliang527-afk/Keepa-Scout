# Keepa Scout API — 中文说明

## 我们的目标是什么

帮做亚马逊转售（Amazon Arbitrage）的人，从海量商品里**找到能赚钱的ASIN**。

具体来说：用户给我们一个商品ID（ASIN），我们回答三个问题：

1. **这个商品能不能卖？** （5条规则全部通过才行）
2. **能赚多少钱？** （计算ROI，投资回报率）
3. **我可以用自然语言问问题吗？** 比如"有多少商品符合条件？"

---

## 我们做了哪些事

### 一套完整的 API 服务（5个接口）

| 接口 | 干什么 |
|---|---|
| `GET /upc` | 条形码 → 找ASIN |
| `GET /eligibility/{asin}` | 单个商品 → 能不能卖 + 能赚多少 |
| `POST /eligibility/batch` | 批量检查多个商品 |
| `POST /ask` | 自然语言问问题 → AI生成SQL → 查数据库 → 回答 |
| `POST /chat` | 多轮对话，支持"上一个结果里第二个"这种指代 |

---

## 达成的主要目标

### ✅ 批量 eligibility 检查
ETL 脚本从 Keepa 拉数据存到 SQLite，问 5 条规则：

| 规则 | 含义 | 阈值 |
|---|---|---|
| referral_fee_pct | Amazon 收的佣金比例 | 必须 > 0 |
| demand（销量） | 有没有人买 | 排名≤10万 或 月销≥100 |
| buybox | 黄金购物车价格 | ≥ $10 |
| amazon_pct | Amazon自营占比 | ≤ 80% |
| monthly_sold | 月销量 | null 或 ≥ 100 |

### ✅ ROI 计算
```
利润 = 卖价 - Amazon佣金 - FBA打包费 - $0.50仓储
ROI = 利润 / 进货成本 × 100%
```

### ✅ 自然语言问问题
用 DeepSeek AI，把你的问题转成 SQL 语句，安全执行，再把结果用自然语言回答你。

### ✅ 多轮对话记忆
聊完"给我高ROI的" → 再问"加个价格限制" → 系统记得你之前筛的是什么。

---

## Amazon 内部术语解释表

> 以下术语是美国亚马逊内部概念，对应英文原词，供你对照理解：

| 中文常用说法 | 英文术语 | 解释 |
|---|---|---|
| ASIN | ASIN | Amazon 商品ID，10位字母数字，如 B00HEON30Y，类似于淘宝的"商品链接ID" |
| BuyBox | BuyBox / Buy Box | 页面右上角那个"加入购物车"按钮区域。谁赢得BuyBox，谁就能得到大多数订单 |
| 黄金购物车 | BuyBox | 同上，中文俗称"黄金购物车" |
| 跟卖 | Arbitrage / Retail Arbitrage | 买进别人已经上架的商品，在亚马逊上转卖，赚差价 |
| 佣金 | Referral Fee | Amazon 每卖出一件收的手续费，按销售额比例收，类目不同比例不同（6%~17%） |
| FBA 打包费 | FBA Pick & Pack Fee | Amazon 帮你拣货、打包、发货的服务费，按件收 |
| 销售排名 | Sales Rank / BSR (Best Sellers Rank) | 这个商品在亚马逊所有商品里的销量排名。排名越小卖得越好 |
| 月销量 | Monthly Sold | 每月估算卖出多少件 |
| 亚马逊自营占比 | Amazon BuyBox % | 亚马逊自营赢得购物车的比例，太高说明竞争激烈不适合跟卖 |
| 供货商成本 | Supplier Cost | 你从批发商/零售商买这个商品花了多少钱 |
| 利润 | Payout / Net | 卖一件到手的钱（扣除所有费用后） |
| ROI | ROI (Return on Investment) | 投资回报率，公式：(利润 / 成本) × 100% |
| 转售 | Resell / Arbitrage | 买进再卖出 |
| Keepa | Keepa | 抓取亚马逊历史数据的第三方工具，可以看到价格、排名变化 |
| UPC | UPC (Universal Product Code) | 商品条形码，12位数字，贴在每个零售商品上 |
| EAN | EAN (European Article Number) | 欧洲版UPC，13位，和UPC功能一样 |
| ISBN | ISBN | 书籍专用码，10位或13位 |
| UPC-E | UPC-E | 缩写版条形码，6-8位，展开后是12位UPC-A |

---

## 技术架构（简化说明）

```
你问问题（自然语言）
       ↓
DeepSeek AI 转成 SQL 语句
       ↓
安全检查（只允许 SELECT，禁止删除/修改）
       ↓
查 SQLite 数据库
       ↓
DeepSeek 把数据格式化成自然语言回答
```

数据库里有我们提前从 Keepa 拉好的商品数据（价格、排名、佣金、销量等），每次运行 ETL 脚本更新。

---

## 怎么运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 KEEPA_API_KEYS 和 DEEPSEEK_API_KEY

# 3. 从 Keepa 拉数据（ETL）
python -m app.etl

# 4. 启动服务
uvicorn app.main:app --reload --port 8000
```

打开 http://localhost:8000/docs 可以看到交互式文档，直接在网页上测试每个接口。

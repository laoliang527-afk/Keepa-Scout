"""
数据库配置模块。

提供：
  - 异步 SQLite 引擎（aiosqlite + SQLAlchemy）
  - 异步会话工厂 async_session_maker
  - init_db() — 建表
  - get_db() — 依赖注入上下文管理器（用于 FastAPI）
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# 加载 .env 中的环境变量（如 DB_PATH、KEEPA_API_KEY 等）
load_dotenv()

# 数据库文件路径，默认放在 data/scout.db
# 支持绝对路径或相对于项目根目录的相对路径
DB_PATH = os.getenv("DB_PATH", "data/scout.db")
if not os.path.isabs(DB_PATH):
    # app/database.py 位于 app/ 目录下，向上一级即项目根目录
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), DB_PATH)

# 异步 SQLite 连接 URL（sqlite+aiosqlite:/// 是 aiosqlite 驱动的固定格式）
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# 创建异步引擎，expire_on_commit=False 防止提交后访问已分离的对象
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# 所有 ORM 模型的基类（由 app/models.py 中的模型继承）
class Base(DeclarativeBase):
    pass


async def init_db():
    """初始化数据库：创建所有表（仅当表不存在时）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_db():
    """
    FastAPI 依赖注入：自动管理会话的提交与回滚。
    用法：
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

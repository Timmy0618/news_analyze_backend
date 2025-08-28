"""
SQLAlchemy 資料庫連接設定
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from models import Base

try:
    from config import Config
    # 使用配置文件中的資料庫URL
    DATABASE_URL = Config.get_database_url()
    print(f"使用配置的資料庫: {Config.DATABASE_TYPE}")
except ImportError:
    # 如果沒有配置文件，使用默認的SQLite設定
    DATABASE_URL = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'news.db')}"
    print("使用默認SQLite資料庫設定")

# 創建引擎
engine = create_engine(
    DATABASE_URL,
    echo=False,  # 設為 True 可以看到 SQL 查詢
    pool_pre_ping=True
)

# 創建 Session 類
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """創建所有資料表"""
    Base.metadata.create_all(bind=engine)
    print("資料表創建完成")


@contextmanager
def get_db_session():
    """
    獲取資料庫 session 的上下文管理器
    
    Usage:
        with get_db_session() as session:
            # 使用 session 進行資料庫操作
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_session() -> Session:
    """
    獲取新的資料庫 session
    注意：使用完畢後需要手動關閉 session
    """
    return SessionLocal()


# 初始化資料庫表格
def init_database():
    """初始化資料庫"""
    try:
        create_tables()
        print("資料庫初始化完成")
    except Exception as e:
        print(f"資料庫初始化失敗: {e}")

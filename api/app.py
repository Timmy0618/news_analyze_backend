#!/usr/bin/env python3
"""
新聞 API 應用 - 使用分離的排程器
"""

from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
import os
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from dotenv import load_dotenv

# 匯入分離的排程器
from .scheduler import start_scheduler, stop_scheduler, get_scheduler_status, get_scheduler_interval, run_scraper_job

# 載入環境變數
load_dotenv()

# 設定日誌
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("news_api")
logger.setLevel(logging.INFO)

# 清除現有的 handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# 設定格式
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 時間輪轉文件處理器
file_handler = TimedRotatingFileHandler(
    filename=LOG_DIR / "api.log",
    when='midnight',
    interval=1,
    backupCount=7,
    encoding='utf-8'
)
file_handler.setFormatter(formatter)
file_handler.suffix = "%Y%m%d"

# 控制台處理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# 添加處理器
logger.addHandler(file_handler)
logger.addHandler(console_handler)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用生命周期管理"""
    # 啟動時
    logger.info("🚀 新聞 API 服務啟動")
    
    # 啟動排程器
    interval = get_scheduler_interval()
    await start_scheduler(interval)
    logger.info(f"📅 排程器已啟動 - 每 {interval} 小時執行爬蟲")
    
    yield
    
    # 關閉時
    logger.info("👋 正在關閉新聞 API 服務")
    await stop_scheduler()

app = FastAPI(
    title="新聞 API with Scheduler",
    description="提供新聞數據的 RESTful API，內建自動爬蟲排程",
    version="2.0.0",
    lifespan=lifespan
)

# 資料庫配置
def get_database_url():
    """獲取資料庫連線 URL"""
    database_type = os.getenv('DATABASE_TYPE', 'sqlite')
    
    if database_type == 'postgresql':
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = os.getenv('POSTGRES_PORT', '5432')
        database = os.getenv('POSTGRES_DATABASE', 'news_analyze')
        user = os.getenv('POSTGRES_USER', 'news_user')
        password = os.getenv('POSTGRES_PASSWORD', 'news_password_2024')
        return f'postgresql://{user}:{password}@{host}:{port}/{database}'
    else:
        sqlite_path = os.getenv('SQLITE_DB_PATH', './news.db')
        return f'sqlite:///{sqlite_path}'

# 建立資料庫連線
engine = create_engine(get_database_url())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 依賴注入：獲取資料庫會話
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic 模型
class NewsResponse(BaseModel):
    id: int
    title: str
    content: Optional[str] = None
    url: Optional[str] = None
    source: str
    publish_time: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

class NewsListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int
    data: List[NewsResponse]

class StatsResponse(BaseModel):
    total_news: int
    sources: Dict[str, int]
    latest_update: Optional[datetime] = None

class SchedulerStatusResponse(BaseModel):
    status: str
    interval_hours: int
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None

# API 路由
@app.get("/")
async def root():
    """根路由"""
    interval = get_scheduler_interval()
    return {
        "message": "新聞 API 服務器 with Scheduler",
        "version": "2.0.0",
        "docs": "/docs",
        "scheduler": {
            "enabled": True,
            "interval_hours": interval
        }
    }

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """健康檢查"""
    try:
        # 測試資料庫連線
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        
        # 獲取排程器狀態
        scheduler_status = get_scheduler_status()
        
        return {
            "status": "healthy",
            "database": "connected",
            "scheduler": scheduler_status["status"],
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"健康檢查失敗: {e}")
        raise HTTPException(status_code=503, detail="服務暫時不可用")

@app.post("/scraper/run")
async def run_scraper_manually(background_tasks: BackgroundTasks):
    """手動執行爬蟲"""
    try:
        background_tasks.add_task(run_scraper_job)
        logger.info("🔄 手動爬蟲任務已加入背景執行")
        
        return {
            "message": "爬蟲任務已開始執行",
            "status": "running",
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"手動執行爬蟲失敗: {e}")
        raise HTTPException(status_code=500, detail="無法執行爬蟲任務")

@app.get("/scheduler/status")
async def get_scheduler_status_api():
    """獲取排程器狀態"""
    try:
        status_info = get_scheduler_status()
        interval = get_scheduler_interval()
        
        # 計算下次執行時間
        now = datetime.now()
        if interval == 24:
            next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
        else:
            next_run = now + timedelta(hours=interval)
        
        return {
            "status": status_info["status"],
            "interval_hours": interval,
            "next_run": next_run,
            "last_run": None  # TODO: 實作上次執行時間追蹤
        }
    except Exception as e:
        logger.error(f"獲取排程器狀態失敗: {e}")
        raise HTTPException(status_code=500, detail="無法獲取排程器狀態")

@app.get("/news", response_model=NewsListResponse)
async def get_news(
    page: int = Query(1, ge=1, description="頁碼"),
    per_page: int = Query(20, ge=1, le=100, description="每頁數量"),
    source: Optional[str] = Query(None, description="新聞來源過濾"),
    search: Optional[str] = Query(None, description="標題搜尋關鍵字"),
    start_date: Optional[str] = Query(None, description="開始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="結束日期 (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """獲取新聞列表"""
    try:
        # 建構查詢條件
        conditions = []
        params = {}
        
        if source:
            conditions.append("source = :source")
            params['source'] = source
        
        if search:
            conditions.append("title LIKE :search")
            params['search'] = f"%{search}%"
        
        if start_date:
            conditions.append("DATE(created_at) >= :start_date")
            params['start_date'] = start_date
        
        if end_date:
            conditions.append("DATE(created_at) <= :end_date")
            params['end_date'] = end_date
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # 計算總數
        count_query = f"SELECT COUNT(*) FROM news WHERE {where_clause}"
        total_result = db.execute(text(count_query), params)
        total = total_result.scalar() or 0
        
        # 計算分頁
        offset = (page - 1) * per_page
        pages = (total + per_page - 1) // per_page
        
        # 獲取數據
        data_query = f"""
            SELECT id, title, content, url, source, publish_time, created_at, updated_at
            FROM news 
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """
        params.update({'limit': per_page, 'offset': offset})
        
        result = db.execute(text(data_query), params)
        rows = result.fetchall()
        
        # 轉換為響應模型
        news_data = []
        for row in rows:
            news_item = NewsResponse(
                id=row[0],
                title=row[1] or "",
                content=row[2],
                url=row[3],
                source=row[4] or "",
                publish_time=row[5],
                created_at=row[6],
                updated_at=row[7]
            )
            news_data.append(news_item)
        
        return NewsListResponse(
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
            data=news_data
        )
        
    except Exception as e:
        logger.error(f"獲取新聞列表失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取新聞列表失敗")

@app.get("/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    """獲取統計信息"""
    try:
        # 總新聞數
        total_query = "SELECT COUNT(*) FROM news"
        total_result = db.execute(text(total_query))
        total_news = total_result.scalar() or 0
        
        # 各來源統計
        sources_query = "SELECT source, COUNT(*) FROM news GROUP BY source"
        sources_result = db.execute(text(sources_query))
        sources = {row[0]: row[1] for row in sources_result.fetchall()}
        
        # 最新更新時間
        latest_query = "SELECT MAX(created_at) FROM news"
        latest_result = db.execute(text(latest_query))
        latest_update = latest_result.scalar()
        
        return StatsResponse(
            total_news=total_news,
            sources=sources,
            latest_update=latest_update
        )
        
    except Exception as e:
        logger.error(f"獲取統計信息失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取統計信息失敗")

@app.get("/news/recent")
async def get_recent_news(
    limit: int = Query(10, ge=1, le=50, description="返回數量"),
    source: Optional[str] = Query(None, description="新聞來源過濾"),
    db: Session = Depends(get_db)
):
    """獲取最新新聞"""
    try:
        conditions = []
        params = {'limit': limit}
        
        if source:
            conditions.append("source = :source")
            params['source'] = source
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT id, title, url, source, publish_time, created_at
            FROM news 
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit
        """
        
        result = db.execute(text(query), params)
        rows = result.fetchall()
        
        news_data = []
        for row in rows:
            news_data.append({
                "id": row[0],
                "title": row[1],
                "url": row[2],
                "source": row[3],
                "publish_time": row[4],
                "created_at": row[5]
            })
        
        return {
            "count": len(news_data),
            "data": news_data
        }
        
    except Exception as e:
        logger.error(f"獲取最新新聞失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取最新新聞失敗")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

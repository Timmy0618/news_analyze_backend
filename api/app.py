#!/usr/bin/env python3
"""
新聞 API 應用 - 使用分離的排程器 (MongoDB 版本)
"""

from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
import os
from contextlib import asynccontextmanager
from pydantic import BaseModel
from dotenv import load_dotenv

# 匯入 MongoDB 相關模組
from db.database_mongodb import init_mongodb, close_mongodb, get_mongodb_connection
from db.news_mongodb import get_news_mongo_db

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
    logger.info("🚀 新聞 API 服務啟動 (MongoDB版本)")
    
    # 初始化 MongoDB 連接
    try:
        if not init_mongodb():
            logger.error("MongoDB 連接失敗")
            raise RuntimeError("無法連接到 MongoDB")
        logger.info("📦 MongoDB 連接成功")
    except Exception as e:
        logger.error(f"MongoDB 初始化失敗: {e}")
        raise
    
    # 啟動排程器
    interval = get_scheduler_interval()
    await start_scheduler(interval)
    logger.info(f"📅 排程器已啟動 - 每 {interval} 小時執行爬蟲")
    
    yield
    
    # 關閉時
    logger.info("👋 正在關閉新聞 API 服務")
    await stop_scheduler()
    close_mongodb()

app = FastAPI(
    title="新聞 API with Scheduler (MongoDB)",
    description="提供新聞數據的 RESTful API，內建自動爬蟲排程 (使用 MongoDB)",
    version="2.0.0-mongodb",
    lifespan=lifespan
)

# 添加 CORS 中間件，支持前端跨域請求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生產環境中應該指定具體的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB 依賴注入
def get_mongo_db():
    """獲取 MongoDB 連接"""
    connection = get_mongodb_connection()
    if not connection.is_connected():
        raise HTTPException(status_code=503, detail="MongoDB 連接不可用")
    return get_news_mongo_db()

# Pydantic 模型
class NewsResponse(BaseModel):
    pk: str  # MongoDB ObjectId 作為字串
    news_id: str
    news_source: str
    author: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    publish_time: Optional[str] = None
    create_time: Optional[datetime] = None

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
async def health_check():
    """健康檢查"""
    try:
        # 測試 MongoDB 連接
        connection = get_mongodb_connection()
        if not connection.is_connected():
            raise HTTPException(status_code=503, detail="MongoDB 連接不可用")
        
        # 獲取排程器狀態
        scheduler_status = get_scheduler_status()
        
        # 獲取 MongoDB 資料庫資訊
        db_info = connection.get_database_info()
        
        return {
            "status": "healthy",
            "database": "connected",
            "database_info": {
                "type": "MongoDB",
                "collections": db_info.get("collections_count", 0),
                "data_size": db_info.get("data_size", 0)
            },
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
    source: Optional[str] = Query(None, description="新聞來源過濾 (SETN, LTN, TVBS, ChinaTimes)"),
    search: Optional[str] = Query(None, description="標題搜尋關鍵字"),
    author: Optional[str] = Query(None, description="作者過濾"),
    start_date: Optional[str] = Query(None, description="開始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="結束日期 (YYYY-MM-DD)"),
    sort_by: str = Query("create_time", description="排序欄位 (create_time, publish_time, title)"),
    sort_order: str = Query("desc", description="排序方向 (asc, desc)"),
    mongo_db = Depends(get_mongo_db)
):
    """獲取新聞列表 - 支持多種過濾和排序功能"""
    try:
        # 使用 MongoDB 查詢
        result = mongo_db.get_news_by_query(
            page=page,
            per_page=per_page,
            news_source=source,
            search=search,
            author=author,
            start_date=start_date,
            end_date=end_date,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # 轉換為響應模型
        news_data = []
        for news_dict in result['data']:
            # 解析 create_time 字串為 datetime 對象
            create_time = None
            if news_dict.get('create_time'):
                try:
                    if isinstance(news_dict['create_time'], str):
                        create_time = datetime.fromisoformat(news_dict['create_time'].replace('Z', '+00:00'))
                    else:
                        create_time = news_dict['create_time']
                except:
                    create_time = None
            
            news_item = NewsResponse(
                pk=news_dict.get('pk', ''),
                news_id=news_dict.get('news_id', ''),
                news_source=news_dict.get('news_source', ''),
                author=news_dict.get('author'),
                title=news_dict.get('title'),
                url=news_dict.get('url'),
                publish_time=news_dict.get('publish_time'),
                create_time=create_time
            )
            news_data.append(news_item)
        
        return NewsListResponse(
            total=result['total'],
            page=result['page'],
            per_page=result['per_page'],
            pages=result['pages'],
            data=news_data
        )
        
    except Exception as e:
        logger.error(f"獲取新聞列表失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取新聞列表失敗")

@app.get("/stats", response_model=StatsResponse)
async def get_stats(mongo_db = Depends(get_mongo_db)):
    """獲取統計信息"""
    try:
        # 使用 MongoDB 獲取統計資訊
        stats = mongo_db.get_stats()
        
        return StatsResponse(
            total_news=stats['total_news'],
            sources=stats['sources'],
            latest_update=stats['latest_update']
        )
        
    except Exception as e:
        logger.error(f"獲取統計信息失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取統計信息失敗")

@app.get("/news/recent")
async def get_recent_news(
    limit: int = Query(10, ge=1, le=50, description="返回數量"),
    source: Optional[str] = Query(None, description="新聞來源過濾"),
    sort_by: str = Query("create_time", description="排序欄位"),
    mongo_db = Depends(get_mongo_db)
):
    """獲取最新新聞"""
    try:
        # 如果有來源過濾，使用查詢功能
        if source:
            result = mongo_db.get_news_by_query(
                page=1,
                per_page=limit,
                news_source=source,
                sort_by=sort_by,
                sort_order="desc"
            )
            news_data = result['data']
        else:
            # 直接獲取最新新聞
            news_data = mongo_db.get_recent_news(limit)
        
        # 轉換格式以符合原 API 響應
        formatted_data = []
        for news_dict in news_data:
            # 解析 create_time
            create_time = None
            if news_dict.get('create_time'):
                try:
                    if isinstance(news_dict['create_time'], str):
                        create_time = datetime.fromisoformat(news_dict['create_time'].replace('Z', '+00:00'))
                    else:
                        create_time = news_dict['create_time']
                except:
                    create_time = None
            
            formatted_data.append({
                "pk": news_dict.get('pk', ''),
                "news_id": news_dict.get('news_id', ''),
                "title": news_dict.get('title', ''),
                "url": news_dict.get('url', ''),
                "news_source": news_dict.get('news_source', ''),
                "author": news_dict.get('author', ''),
                "publish_time": news_dict.get('publish_time'),
                "create_time": create_time
            })
        
        return {
            "count": len(formatted_data),
            "data": formatted_data
        }
        
    except Exception as e:
        logger.error(f"獲取最新新聞失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取最新新聞失敗")

@app.get("/news/sources")
async def get_news_sources(mongo_db = Depends(get_mongo_db)):
    """獲取所有新聞來源列表"""
    try:
        sources_data = mongo_db.get_news_count_by_source()
        sources = []
        
        for source_name, count in sources_data:
            sources.append({
                "name": source_name,
                "count": count,
                "display_name": {
                    "SETN": "三立新聞",
                    "LTN": "自由時報",
                    "TVBS": "TVBS新聞",
                    "ChinaTimes": "中時新聞"
                }.get(source_name, source_name)
            })
        
        return {
            "sources": sources,
            "total_sources": len(sources)
        }
        
    except Exception as e:
        logger.error(f"獲取新聞來源失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取新聞來源失敗")

@app.get("/news/search")
async def search_news(
    q: str = Query(..., description="搜尋關鍵字"),
    page: int = Query(1, ge=1, description="頁碼"),
    per_page: int = Query(20, ge=1, le=50, description="每頁數量"),
    source: Optional[str] = Query(None, description="新聞來源過濾"),
    sort_by: str = Query("create_time", description="排序欄位"),
    sort_order: str = Query("desc", description="排序方向"),
    mongo_db = Depends(get_mongo_db)
):
    """搜尋新聞"""
    try:
        result = mongo_db.get_news_by_query(
            page=page,
            per_page=per_page,
            news_source=source,
            search=q,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # 轉換為響應格式
        news_data = []
        for news_dict in result['data']:
            create_time = None
            if news_dict.get('create_time'):
                try:
                    if isinstance(news_dict['create_time'], str):
                        create_time = datetime.fromisoformat(news_dict['create_time'].replace('Z', '+00:00'))
                    else:
                        create_time = news_dict['create_time']
                except:
                    create_time = None
            
            news_item = NewsResponse(
                pk=news_dict.get('pk', ''),
                news_id=news_dict.get('news_id', ''),
                news_source=news_dict.get('news_source', ''),
                author=news_dict.get('author'),
                title=news_dict.get('title'),
                url=news_dict.get('url'),
                publish_time=news_dict.get('publish_time'),
                create_time=create_time
            )
            news_data.append(news_item)
        
        return NewsListResponse(
            total=result['total'],
            page=result['page'],
            per_page=result['per_page'],
            pages=result['pages'],
            data=news_data
        )
        
    except Exception as e:
        logger.error(f"搜尋新聞失敗: {e}")
        raise HTTPException(status_code=500, detail="搜尋新聞失敗")

@app.get("/news/{news_id}")
async def get_news_detail(
    news_id: str,
    mongo_db = Depends(get_mongo_db)
):
    """獲取單條新聞詳情"""
    try:
        from bson import ObjectId
        from db.models_mongodb import News
        
        # 驗證 ObjectId 格式
        try:
            obj_id = ObjectId(news_id)
        except:
            raise HTTPException(status_code=400, detail="無效的新聞ID格式")
        
        # 根據 ObjectId 查找
        news = News.objects(id=obj_id).first()
        if not news:
            raise HTTPException(status_code=404, detail="新聞未找到")
        
        news_dict = news.to_dict()
        create_time = None
        if news_dict.get('create_time'):
            try:
                if isinstance(news_dict['create_time'], str):
                    create_time = datetime.fromisoformat(news_dict['create_time'].replace('Z', '+00:00'))
                else:
                    create_time = news_dict['create_time']
            except:
                create_time = None
        
        return NewsResponse(
            pk=news_dict.get('pk', ''),
            news_id=news_dict.get('news_id', ''),
            news_source=news_dict.get('news_source', ''),
            author=news_dict.get('author'),
            title=news_dict.get('title'),
            url=news_dict.get('url'),
            publish_time=news_dict.get('publish_time'),
            create_time=create_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取新聞詳情失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取新聞詳情失敗")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

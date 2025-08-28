#!/usr/bin/env python3
"""
排程器模組
負責自動執行爬蟲任務
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

# 設定日誌
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def setup_scheduler_logger():
    """設定排程器日誌"""
    logger = logging.getLogger("scheduler")
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
        filename=LOG_DIR / "scheduler.log",
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
    
    return logger

# 全域變數
scheduler_task: Optional[asyncio.Task] = None
scheduler_logger = setup_scheduler_logger()

async def run_scraper_job() -> dict:
    """執行爬蟲任務"""
    try:
        scheduler_logger.info("=" * 60)
        scheduler_logger.info("開始執行排程爬蟲任務")
        scheduler_logger.info(f"執行時間: {datetime.now()}")
        scheduler_logger.info("=" * 60)
        
        # 在新線程中執行爬蟲（避免阻塞 FastAPI）
        def scraper_worker():
            try:
                from unified_manager_orm import UnifiedScraperManager
                scraper_manager = UnifiedScraperManager()
                results = scraper_manager.run_all_scrapers(max_pages=3)
                
                # 記錄執行結果
                if '總計' in results:
                    total = results['總計']
                    scheduler_logger.info(f"✅ 爬蟲任務執行成功 - 總計:{total.get('total', 0)}, 新增:{total.get('new', 0)}, 跳過:{total.get('skipped', 0)}, 失敗:{total.get('failed', 0)}")
                
                return results
            except Exception as e:
                scheduler_logger.error(f"❌ 爬蟲任務執行異常: {e}")
                import traceback
                scheduler_logger.error(f"詳細錯誤: {traceback.format_exc()}")
                return {"error": str(e)}
        
        # 在線程池中執行
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, scraper_worker)
        
        scheduler_logger.info("=" * 60)
        scheduler_logger.info("排程爬蟲任務結束")
        scheduler_logger.info("=" * 60)
        
        return result
        
    except Exception as e:
        scheduler_logger.error(f"❌ 排程任務執行異常: {e}")
        import traceback
        scheduler_logger.error(f"詳細錯誤: {traceback.format_exc()}")
        return {"error": str(e)}

async def run_scheduler(interval_hours: int = 24):
    """運行排程器"""
    scheduler_logger.info(f"📅 排程器啟動 - 每 {interval_hours} 小時執行一次")
    
    # 計算下次執行時間
    if interval_hours == 24:
        # 24小時的話，設定在凌晨2點執行
        now = datetime.now()
        next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        
        wait_seconds = (next_run - now).total_seconds()
        scheduler_logger.info(f"📅 下次執行時間: {next_run}, 等待 {wait_seconds/3600:.1f} 小時")
        
        # 等待到指定時間
        await asyncio.sleep(wait_seconds)
    
    while True:
        try:
            # 執行爬蟲任務
            await run_scraper_job()
            
            # 等待下次執行
            wait_seconds = interval_hours * 3600
            scheduler_logger.info(f"📅 等待 {interval_hours} 小時後執行下次任務")
            await asyncio.sleep(wait_seconds)
            
        except asyncio.CancelledError:
            scheduler_logger.info("📅 排程器收到取消信號")
            break
        except Exception as e:
            scheduler_logger.error(f"❌ 排程器異常: {e}")
            # 等待一段時間後重試
            await asyncio.sleep(300)  # 5分鐘後重試

async def start_scheduler(interval_hours: int = 24) -> asyncio.Task:
    """啟動排程器"""
    global scheduler_task
    
    if scheduler_task and not scheduler_task.done():
        scheduler_logger.info("📅 排程器已在運行中")
        return scheduler_task
    
    scheduler_task = asyncio.create_task(run_scheduler(interval_hours))
    scheduler_logger.info(f"📅 排程器已啟動 - 每 {interval_hours} 小時執行爬蟲")
    
    # 立即執行一次爬蟲任務
    scheduler_logger.info("🚀 排程器啟動時立即執行一次爬蟲任務")
    asyncio.create_task(run_scraper_job())
    
    return scheduler_task

async def stop_scheduler():
    """停止排程器"""
    global scheduler_task
    
    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            scheduler_logger.info("📅 排程器已停止")
        scheduler_task = None

def get_scheduler_status() -> dict:
    """獲取排程器狀態"""
    global scheduler_task
    
    status = "running" if scheduler_task and not scheduler_task.done() else "stopped"
    
    return {
        "status": status,
        "task_done": scheduler_task.done() if scheduler_task else True,
        "task_cancelled": scheduler_task.cancelled() if scheduler_task else False
    }

def get_scheduler_interval() -> int:
    """從環境變數獲取排程間隔"""
    scheduler_interval_env = os.getenv('SCHEDULER_INTERVAL')
    if scheduler_interval_env:
        try:
            return int(scheduler_interval_env)
        except ValueError:
            scheduler_logger.warning("SCHEDULER_INTERVAL 環境變數格式錯誤，使用預設值 24 小時")
    
    return 24

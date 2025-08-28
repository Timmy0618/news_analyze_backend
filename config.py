"""
配置管理模組
從 .env 文件讀取配置
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# 載入 .env 文件
load_dotenv()

class Config:
    """配置類"""
    
    # 資料庫設定
    DATABASE_TYPE = os.getenv('DATABASE_TYPE', 'sqlite')
    
    # SQLite 設定
    SQLITE_DB_PATH = os.getenv('SQLITE_DB_PATH', './news.db')
    
    # PostgreSQL 設定
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
    POSTGRES_DATABASE = os.getenv('POSTGRES_DATABASE', 'news_analyze')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'news_user')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')
    
    # 其他設定
    DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # 爬蟲設定
    MAX_CONCURRENT_SCRAPERS = int(os.getenv('MAX_CONCURRENT_SCRAPERS', 4))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 30))
    RETRY_ATTEMPTS = int(os.getenv('RETRY_ATTEMPTS', 3))
    DELAY_BETWEEN_REQUESTS = int(os.getenv('DELAY_BETWEEN_REQUESTS', 2))
    
    # 新聞來源啟用狀態
    ENABLE_SETN = os.getenv('ENABLE_SETN', 'true').lower() == 'true'
    ENABLE_LTN = os.getenv('ENABLE_LTN', 'true').lower() == 'true'
    ENABLE_TVBS = os.getenv('ENABLE_TVBS', 'true').lower() == 'true'
    ENABLE_CHINATIMES = os.getenv('ENABLE_CHINATIMES', 'true').lower() == 'true'
    
    @classmethod
    def get_database_url(cls) -> str:
        """
        根據設定返回資料庫連接字串
        """
        if cls.DATABASE_TYPE == 'sqlite':
            # 確保使用絕對路徑
            db_path = Path(cls.SQLITE_DB_PATH).resolve()
            return f"sqlite:///{db_path}"
        elif cls.DATABASE_TYPE == 'postgresql':
            return (f"postgresql://{cls.POSTGRES_USER}:{cls.POSTGRES_PASSWORD}"
                   f"@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DATABASE}")
        else:
            raise ValueError(f"不支援的資料庫類型: {cls.DATABASE_TYPE}")
    
    @classmethod
    def get_enabled_scrapers(cls) -> list:
        """
        返回啟用的爬蟲列表
        """
        enabled = []
        if cls.ENABLE_SETN:
            enabled.append('SETN')
        if cls.ENABLE_LTN:
            enabled.append('LTN')
        if cls.ENABLE_TVBS:
            enabled.append('TVBS')
        if cls.ENABLE_CHINATIMES:
            enabled.append('ChinaTimes')
        return enabled
    
    @classmethod
    def print_config(cls):
        """
        打印當前配置（隱藏敏感信息）
        """
        print("📋 當前配置:")
        print(f"  資料庫類型: {cls.DATABASE_TYPE}")
        if cls.DATABASE_TYPE == 'sqlite':
            print(f"  SQLite 路徑: {cls.SQLITE_DB_PATH}")
        else:
            print(f"  PostgreSQL 主機: {cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}")
            print(f"  PostgreSQL 資料庫: {cls.POSTGRES_DATABASE}")
            print(f"  PostgreSQL 用戶: {cls.POSTGRES_USER}")
        print(f"  除錯模式: {cls.DEBUG}")
        print(f"  日誌等級: {cls.LOG_LEVEL}")
        print(f"  最大並行爬蟲: {cls.MAX_CONCURRENT_SCRAPERS}")
        print(f"  啟用的爬蟲: {', '.join(cls.get_enabled_scrapers())}")

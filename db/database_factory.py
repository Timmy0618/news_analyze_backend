"""
資料庫工廠 - 根據配置選擇合適的資料庫實現
"""
import os
from typing import Any


class DatabaseFactory:
    """資料庫工廠類，根據配置創建合適的資料庫實例"""
    
    @staticmethod
    def create_database():
        """根據環境變數創建資料庫實例"""
        database_type = os.getenv('DATABASE_TYPE', 'postgresql').lower()
        
        if database_type == 'mongodb':
            from .news_mongodb import news_mongo_db
            print("使用 MongoDB 資料庫")
            return news_mongo_db
        elif database_type == 'postgresql':
            # 保留原有的 PostgreSQL 支援
            try:
                from .news_orm_db import news_orm_db
                print("使用 PostgreSQL 資料庫")
                return news_orm_db
            except ImportError:
                print("PostgreSQL 模組未找到，回退到 SQLite")
                from .news_orm_db import news_orm_db
                return news_orm_db
        elif database_type == 'sqlite':
            try:
                from .news_orm_db import news_orm_db
                print("使用 SQLite 資料庫")
                return news_orm_db
            except ImportError:
                print("SQLite 模組未找到")
                raise ImportError("無法載入資料庫模組")
        else:
            raise ValueError(f"不支援的資料庫類型: {database_type}")


# 全域資料庫實例
def get_database():
    """獲取資料庫實例"""
    return DatabaseFactory.create_database()

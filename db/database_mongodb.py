"""
MongoDB 資料庫連接設定
"""
import os
from typing import Optional
import logging
from mongoengine import connect, disconnect
from pymongo.errors import ServerSelectionTimeoutError

logger = logging.getLogger(__name__)


class MongoDBConnection:
    """MongoDB 連接管理類"""
    
    def __init__(self):
        self.connected = False
        self.connection = None
    
    def get_connection_string(self) -> str:
        """獲取 MongoDB 連接字串"""
        # 優先使用完整的連接字串
        connection_string = os.getenv('MONGODB_CONNECTION_STRING')
        if connection_string:
            return connection_string
        
        # 否則從個別參數組合
        host = os.getenv('MONGODB_HOST', 'localhost')
        port = os.getenv('MONGODB_PORT', '27017')
        database = os.getenv('MONGODB_DATABASE', 'news_analyze')
        user = os.getenv('MONGODB_USER')
        password = os.getenv('MONGODB_PASSWORD')
        
        if user and password:
            return f"mongodb://{user}:{password}@{host}:{port}/{database}"
        else:
            return f"mongodb://{host}:{port}/{database}"
    
    def connect(self) -> bool:
        """連接到 MongoDB"""
        if self.connected:
            logger.info("MongoDB 已經連接")
            return True
        
        try:
            connection_string = self.get_connection_string()
            database = os.getenv('MONGODB_DATABASE', 'news_analyze')
            
            logger.info(f"正在連接到 MongoDB: {database}")
            
            # 使用 MongoEngine 連接
            self.connection = connect(
                db=database,
                host=connection_string,
                serverSelectionTimeoutMS=5000,  # 5秒連接超時
                connectTimeoutMS=10000,  # 10秒連接超時
                socketTimeoutMS=10000,   # 10秒socket超時
            )
            
            # 測試連接
            from mongoengine.connection import get_db
            db = get_db()
            db.list_collection_names()  # 測試操作
            
            self.connected = True
            logger.info("MongoDB 連接成功")
            return True
            
        except ServerSelectionTimeoutError as e:
            logger.error(f"MongoDB 連接超時: {e}")
            return False
        except Exception as e:
            logger.error(f"MongoDB 連接失敗: {e}")
            return False
    
    def disconnect(self):
        """斷開 MongoDB 連接"""
        if self.connected:
            try:
                disconnect()
                self.connected = False
                logger.info("MongoDB 連接已斷開")
            except Exception as e:
                logger.error(f"斷開 MongoDB 連接失敗: {e}")
    
    def is_connected(self) -> bool:
        """檢查是否已連接"""
        return self.connected
    
    def get_database_info(self) -> dict:
        """獲取資料庫資訊"""
        if not self.connected:
            return {'error': 'Not connected to MongoDB'}
        
        try:
            from mongoengine.connection import get_db
            db = get_db()
            
            stats = db.command("dbstats")
            collections = db.list_collection_names()
            
            return {
                'database': db.name,
                'collections': collections,
                'collections_count': len(collections),
                'data_size': stats.get('dataSize', 0),
                'storage_size': stats.get('storageSize', 0),
                'indexes': stats.get('indexes', 0),
            }
        except Exception as e:
            logger.error(f"獲取資料庫資訊失敗: {e}")
            return {'error': str(e)}


# 全域 MongoDB 連接實例
mongodb_connection = MongoDBConnection()


def init_mongodb() -> bool:
    """初始化 MongoDB 連接"""
    return mongodb_connection.connect()


def close_mongodb():
    """關閉 MongoDB 連接"""
    mongodb_connection.disconnect()


def get_mongodb_connection():
    """獲取 MongoDB 連接實例"""
    return mongodb_connection

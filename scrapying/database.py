"""
統一的數據庫管理模組
統一管理新聞爬蟲的SQLite數據庫連接和操作
"""
import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime


class NewsDatabase:
    """新聞數據庫管理類"""
    
    def __init__(self, db_path="news.db"):
        """
        初始化數據庫連接
        
        Args:
            db_path: 數據庫文件路徑，默認為當前目錄下的news.db
        """
        # 如果是相對路徑，則基於scrapying目錄
        if not os.path.isabs(db_path):
            script_dir = os.path.dirname(__file__)
            self.db_path = os.path.join(script_dir, db_path)
        else:
            self.db_path = db_path
            
        # 確保數據庫文件所在目錄存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # 初始化數據庫表
        self._init_tables()
    
    def _init_tables(self):
        """初始化數據庫表結構"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS news (
                id TEXT PRIMARY KEY,
                news_name TEXT,
                author TEXT,
                title TEXT,
                url TEXT,
                publish_time TEXT,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            conn.commit()
    
    @contextmanager
    def get_connection(self):
        """
        獲取數據庫連接的上下文管理器
        使用完後自動關閉連接
        
        Usage:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                # 執行數據庫操作
        """
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()
    
    def insert_news_item(self, news_item):
        """
        插入單條新聞記錄
        
        Args:
            news_item: 新聞字典，包含 id, news_name, author, title, url, publish_time
            
        Returns:
            bool: 插入成功返回True，已存在則返回False
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 檢查是否已存在
            cursor.execute("SELECT id FROM news WHERE id = ?", (news_item["id"],))
            if cursor.fetchone():
                return False  # 已存在
            
            # 插入新記錄
            cursor.execute('''
                INSERT INTO news (id, news_name, author, title, url, publish_time)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                news_item["id"],
                news_item["news_name"], 
                news_item["author"],
                news_item["title"],
                news_item["url"],
                news_item["publish_time"]
            ))
            conn.commit()
            return True
    
    def insert_news_batch(self, news_items):
        """
        批量插入新聞記錄
        
        Args:
            news_items: 新聞字典列表
            
        Returns:
            int: 成功插入的數量
        """
        insert_count = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for item in news_items:
                try:
                    # 檢查是否已存在
                    cursor.execute("SELECT id FROM news WHERE id = ?", (item["id"],))
                    if cursor.fetchone() is None:
                        # 插入新記錄
                        cursor.execute('''
                            INSERT INTO news (id, news_name, author, title, url, publish_time)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            item["id"],
                            item["news_name"],
                            item["author"], 
                            item["title"],
                            item["url"],
                            item["publish_time"]
                        ))
                        insert_count += 1
                except Exception as e:
                    print(f"插入數據時發生錯誤: {e}")
                    continue
            
            conn.commit()
        return insert_count
    
    def news_exists(self, news_id):
        """
        檢查新聞ID是否已存在
        
        Args:
            news_id: 新聞ID
            
        Returns:
            bool: 存在返回True，不存在返回False
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM news WHERE id = ?", (news_id,))
            return cursor.fetchone() is not None
    
    def get_news_by_source(self, news_name, limit=None):
        """
        根據新聞來源獲取新聞列表
        
        Args:
            news_name: 新聞來源名稱
            limit: 限制返回數量
            
        Returns:
            list: 新聞記錄列表
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM news WHERE news_name = ? ORDER BY create_time DESC"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query, (news_name,))
            columns = [description[0] for description in cursor.description]
            
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_latest_news(self, limit=10):
        """
        獲取最新的新聞記錄
        
        Args:
            limit: 限制返回數量，默認10條
            
        Returns:
            list: 新聞記錄列表
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM news ORDER BY create_time DESC LIMIT ?", 
                (limit,)
            )
            columns = [description[0] for description in cursor.description]
            
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_news_count_by_source(self):
        """
        獲取各新聞來源的新聞數量統計
        
        Returns:
            dict: {新聞來源: 數量}
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT news_name, COUNT(*) FROM news GROUP BY news_name")
            return dict(cursor.fetchall())
    
    def delete_news_by_id(self, news_id):
        """
        根據ID刪除新聞記錄
        
        Args:
            news_id: 新聞ID
            
        Returns:
            bool: 刪除成功返回True
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM news WHERE id = ?", (news_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def cleanup_old_news(self, days=30):
        """
        清理指定天數前的舊新聞
        
        Args:
            days: 保留最近多少天的新聞，默認30天
            
        Returns:
            int: 刪除的記錄數量
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM news WHERE create_time < datetime('now', '-{} days')".format(days)
            )
            conn.commit()
            return cursor.rowcount


# 創建全局數據庫實例
# 其他爬蟲可以直接 from database import news_db 來使用
news_db = NewsDatabase()


# 為了向後兼容，提供一些便捷函數
def get_connection():
    """獲取數據庫連接（兼容舊代碼）"""
    return news_db.get_connection()


def create_news_table():
    """創建新聞表（兼容舊代碼）"""
    # 表已經在NewsDatabase初始化時創建了
    pass


def insert_news_to_db(cursor, news_items):
    """
    批量插入新聞到數據庫（兼容舊代碼）
    
    Args:
        cursor: 游標（為了兼容性，實際不使用）
        news_items: 新聞列表
        
    Returns:
        int: 插入成功的數量
    """
    return news_db.insert_news_batch(news_items)


if __name__ == "__main__":
    # 測試代碼
    db = NewsDatabase()
    print("數據庫初始化成功")
    
    # 測試插入
    test_news = {
        "id": "test001",
        "news_name": "測試新聞",
        "author": "測試作者",
        "title": "測試標題", 
        "url": "http://test.com",
        "publish_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    success = db.insert_news_item(test_news)
    print(f"插入測試新聞: {'成功' if success else '已存在'}")
    
    # 測試查詢
    count_by_source = db.get_news_count_by_source()
    print("各來源新聞數量:", count_by_source)
    
    # 清理測試數據
    db.delete_news_by_id("test001")
    print("測試數據已清理")

"""
基於 MongoEngine 的新聞資料庫管理類
"""
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from .database_mongodb import init_mongodb, get_mongodb_connection

logger = logging.getLogger(__name__)


class NewsMongoDatabase:
    """使用 MongoDB 的新聞資料庫管理類"""
    
    def __init__(self):
        """初始化 MongoDB 資料庫"""
        self.connected = init_mongodb()
        if not self.connected:
            raise ConnectionError("無法連接到 MongoDB")
    
    def insert_news_item(self, news_data: Dict[str, Any]) -> bool:
        """
        插入單條新聞記錄
        
        Args:
            news_data: 包含新聞資料的字典
                必須包含: news_id, news_source, title, url
                可選包含: author, publish_time
                
        Returns:
            bool: 插入成功返回 True，已存在返回 False
        """
        try:
            from .models_mongodb import News
            
            # 檢查是否已存在
            news_source = news_data.get('news_source')
            news_id = news_data.get('news_id')
            
            if News.exists(news_source, news_id):
                return False  # 已存在
            
            # 創建新記錄
            news = News.create_from_dict(news_data)
            news.save()
            return True
                
        except Exception as e:
            logger.error(f"插入新聞失敗: {e}")
            return False
    
    def insert_news_batch(self, news_items: List[Dict[str, Any]]) -> int:
        """
        高效率批量插入新聞記錄
        
        Args:
            news_items: 新聞資料列表
            
        Returns:
            int: 成功插入的數量
        """
        if not news_items:
            return 0
            
        insert_count = 0
        
        try:
            from .models_mongodb import News
            
            # 批量檢查已存在的新聞
            existing_pairs = set()
            if news_items:
                # 獲取所有需要檢查的 (news_source, news_id) 對
                check_items = [(item.get('news_source'), item.get('news_id')) for item in news_items]
                
                # 批量查詢已存在的記錄
                for news_source, news_id in check_items:
                    if News.exists(news_source, news_id):
                        existing_pairs.add((news_source, news_id))
            
            # 過濾出需要插入的新聞
            news_to_insert = []
            for item in news_items:
                pair = (item.get('news_source'), item.get('news_id'))
                if pair not in existing_pairs:
                    news = News.create_from_dict(item)
                    news_to_insert.append(news)
            
            # 批量插入
            if news_to_insert:
                # MongoDB 批量插入
                for news in news_to_insert:
                    try:
                        news.save()
                        insert_count += 1
                    except Exception as e:
                        logger.error(f"插入單筆新聞失敗: {e}")
                        continue
                
                logger.info(f"批量插入成功: {insert_count} 條新聞")
            else:
                logger.info("沒有需要插入的新聞（全部已存在）")
        
        except Exception as e:
            logger.error(f"批量插入新聞失敗: {e}")
            # 如果批量插入失敗，回退到逐一插入
            logger.info("回退到逐一插入模式...")
            return self._insert_news_one_by_one(news_items)
        
        return insert_count
    
    def _insert_news_one_by_one(self, news_items: List[Dict[str, Any]]) -> int:
        """
        逐一插入新聞記錄（作為批量插入的備用方案）
        
        Args:
            news_items: 新聞資料列表
            
        Returns:
            int: 成功插入的數量
        """
        insert_count = 0
        
        for item in news_items:
            try:
                if self.insert_news_item(item):
                    insert_count += 1
            except Exception as e:
                logger.error(f"插入單筆新聞失敗: {e} - 標題: {item.get('title', 'unknown')}")
                continue
        
        return insert_count
    
    def news_exists(self, news_source: str, news_id: str) -> bool:
        """
        檢查新聞是否已存在
        
        Args:
            news_source: 新聞來源
            news_id: 新聞ID
            
        Returns:
            bool: 存在返回 True，否則 False
        """
        try:
            from .models_mongodb import News
            return News.exists(news_source, news_id)
        except Exception as e:
            logger.error(f"檢查新聞是否存在時發生錯誤: {e}")
            return False
    
    def get_news_count(self) -> int:
        """獲取新聞總數"""
        try:
            from .models_mongodb import News
            return News.objects.count()
        except Exception as e:
            logger.error(f"獲取新聞總數失敗: {e}")
            return 0
    
    def get_news_count_by_source(self) -> List[tuple]:
        """獲取各新聞來源的新聞數量"""
        try:
            from .models_mongodb import News
            
            # 使用 MongoDB 聚合查詢
            pipeline = [
                {"$group": {"_id": "$news_source", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            
            result = News.objects.aggregate(pipeline)
            return [(item['_id'], item['count']) for item in result]
            
        except Exception as e:
            logger.error(f"獲取各來源新聞數量失敗: {e}")
            return []
    
    def get_recent_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """獲取最近的新聞"""
        try:
            from .models_mongodb import News
            
            news_list = News.objects.order_by('-create_time').limit(limit)
            return [news.to_dict() for news in news_list]
            
        except Exception as e:
            logger.error(f"獲取最近新聞失敗: {e}")
            return []
    
    def get_news_by_query(self, 
                         page: int = 1, 
                         per_page: int = 20,
                         news_source: Optional[str] = None,
                         search: Optional[str] = None,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        根據查詢條件獲取新聞
        
        Args:
            page: 頁碼
            per_page: 每頁數量
            news_source: 新聞來源過濾
            search: 標題搜尋關鍵字
            start_date: 開始日期
            end_date: 結束日期
            
        Returns:
            Dict: 包含新聞列表和分頁資訊的字典
        """
        try:
            from .models_mongodb import News
            
            # 建構查詢條件
            query = {}
            
            if news_source:
                query['news_source'] = news_source
            
            if search:
                query['title__icontains'] = search  # MongoDB 不區分大小寫搜尋
            
            # 日期範圍查詢需要進一步實作，因為 publish_time 是字串格式
            # 這裡暫時跳過，可以後續根據實際需求調整
            
            # 獲取總數
            total = News.objects.filter(**query).count()
            
            # 計算分頁
            offset = (page - 1) * per_page
            pages = (total + per_page - 1) // per_page
            
            # 獲取數據
            news_list = News.objects.filter(**query).order_by('-create_time').skip(offset).limit(per_page)
            
            return {
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': pages,
                'data': [news.to_dict() for news in news_list]
            }
            
        except Exception as e:
            logger.error(f"查詢新聞失敗: {e}")
            return {
                'total': 0,
                'page': page,
                'per_page': per_page,
                'pages': 0,
                'data': []
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取資料庫統計資訊"""
        try:
            total_count = self.get_news_count()
            source_counts = dict(self.get_news_count_by_source())
            
            # 獲取最新更新時間
            from .models_mongodb import News
            latest_news = News.objects.order_by('-create_time').first()
            latest_update = latest_news.create_time if latest_news else None
            
            return {
                'total_news': total_count,
                'sources': source_counts,
                'latest_update': latest_update
            }
        except Exception as e:
            logger.error(f"獲取統計資訊失敗: {e}")
            return {
                'total_news': 0,
                'sources': {},
                'latest_update': None
            }


# 創建全域實例
news_mongo_db = NewsMongoDatabase()

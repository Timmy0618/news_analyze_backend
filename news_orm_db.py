"""
基於 SQLAlchemy ORM 的新聞資料庫管理類
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Dict, Any, Optional
from models import News
from database_orm import get_db_session, init_database


class NewsORMDatabase:
    """使用 ORM 的新聞資料庫管理類"""
    
    def __init__(self):
        """初始化資料庫"""
        init_database()
    
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
            with get_db_session() as session:
                # 檢查是否已存在
                existing = session.query(News).filter(
                    and_(
                        News.news_source == news_data.get('news_source'),
                        News.news_id == news_data.get('news_id')
                    )
                ).first()
                
                if existing:
                    return False  # 已存在
                
                # 創建新記錄
                news = News(
                    news_id=news_data.get('news_id'),
                    news_source=news_data.get('news_source'),
                    author=news_data.get('author', ''),
                    title=news_data.get('title', ''),
                    url=news_data.get('url', ''),
                    publish_time=news_data.get('publish_time', '')
                )
                
                session.add(news)
                session.commit()
                return True
                
        except IntegrityError:
            # 唯一約束違反，資料已存在
            return False
        except Exception as e:
            print(f"插入新聞失敗: {e}")
            return False
    
    def insert_news_batch(self, news_items: List[Dict[str, Any]]) -> int:
        """
        批量插入新聞記錄
        
        Args:
            news_items: 新聞資料列表
            
        Returns:
            int: 成功插入的數量
        """
        insert_count = 0
        
        with get_db_session() as session:
            for item in news_items:
                try:
                    # 檢查是否已存在
                    existing = session.query(News).filter(
                        and_(
                            News.news_source == item.get('news_source'),
                            News.news_id == item.get('news_id')
                        )
                    ).first()
                    
                    if not existing:
                        news = News(
                            news_id=item.get('news_id'),
                            news_source=item.get('news_source'),
                            author=item.get('author', ''),
                            title=item.get('title', ''),
                            url=item.get('url', ''),
                            publish_time=item.get('publish_time', '')
                        )
                        session.add(news)
                        insert_count += 1
                        
                except Exception as e:
                    print(f"插入單筆新聞失敗: {e} - 標題: {item.get('title', 'unknown')}")
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
            with get_db_session() as session:
                exists = session.query(News).filter(
                    and_(
                        News.news_source == news_source,
                        News.news_id == news_id
                    )
                ).first() is not None
                return exists
        except Exception as e:
            print(f"檢查新聞是否存在時發生錯誤: {e}")
            return False
    
    def get_news_count(self) -> int:
        """獲取新聞總數"""
        try:
            with get_db_session() as session:
                return session.query(News).count()
        except Exception as e:
            print(f"獲取新聞總數失敗: {e}")
            return 0
    
    def get_news_count_by_source(self) -> List[tuple]:
        """獲取各新聞來源的新聞數量"""
        try:
            with get_db_session() as session:
                result = session.query(
                    News.news_source,
                    func.count(News.pk).label('count')
                ).group_by(News.news_source).order_by(func.count(News.pk).desc()).all()
                
                return [(row.news_source, row.count) for row in result]
        except Exception as e:
            print(f"獲取各來源新聞數量失敗: {e}")
            return []
    
    def get_recent_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """獲取最近的新聞"""
        try:
            with get_db_session() as session:
                news_list = session.query(News).order_by(
                    News.create_time.desc()
                ).limit(limit).all()
                
                return [news.to_dict() for news in news_list]
        except Exception as e:
            print(f"獲取最近新聞失敗: {e}")
            return []
    
    def migrate_from_old_database(self, old_db_path: Optional[str] = None):
        """
        從舊的資料庫格式遷移資料
        
        Args:
            old_db_path: 舊資料庫路徑，如果不提供則使用預設路徑
        """
        import sqlite3
        import os
        import re
        
        if not old_db_path:
            old_db_path = os.path.join(os.path.dirname(__file__), 'scrapying', 'news_old.db')
        
        if not os.path.exists(old_db_path):
            print("舊資料庫檔案不存在，跳過遷移")
            return
        
        try:
            # 連接舊資料庫
            old_conn = sqlite3.connect(old_db_path)
            old_cursor = old_conn.cursor()
            
            # 檢查舊表結構
            old_cursor.execute("PRAGMA table_info(news)")
            columns = [col[1] for col in old_cursor.fetchall()]
            
            if 'id' in columns and 'news_name' in columns:
                # 舊格式資料
                old_cursor.execute("SELECT id, news_name, author, title, url, publish_time FROM news")
                old_data = old_cursor.fetchall()
                
                migrated_count = 0
                with get_db_session() as session:
                    for row in old_data:
                        old_id, news_name, author, title, url, publish_time = row
                        
                        # 解析新聞來源和ID
                        if old_id.startswith('chinatimes_'):
                            news_source = 'ChinaTimes'
                            news_id = old_id[11:]  # 去除 'chinatimes_' 前綴
                        elif old_id.startswith('tvbs_'):
                            news_source = 'TVBS'
                            news_id = old_id[5:]   # 去除 'tvbs_' 前綴
                        elif old_id.startswith('ltn_'):
                            news_source = 'LTN'
                            news_id = old_id[4:]   # 去除 'ltn_' 前綴
                        elif old_id.startswith('setn_'):
                            news_source = 'SETN'
                            news_id = old_id[5:]   # 去除 'setn_' 前綴
                        else:
                            # 使用 news_name 作為來源
                            news_source = news_name or 'Unknown'
                            news_id = old_id
                        
                        # 檢查是否已存在
                        existing = session.query(News).filter(
                            and_(
                                News.news_source == news_source,
                                News.news_id == news_id
                            )
                        ).first()
                        
                        if not existing:
                            news = News(
                                news_id=news_id,
                                news_source=news_source,
                                author=author or '',
                                title=title or '',
                                url=url or '',
                                publish_time=publish_time or ''
                            )
                            session.add(news)
                            migrated_count += 1
                
                print(f"成功遷移 {migrated_count} 筆舊資料")
            
            old_conn.close()
            
        except Exception as e:
            print(f"資料遷移失敗: {e}")


# 創建全域實例
news_orm_db = NewsORMDatabase()

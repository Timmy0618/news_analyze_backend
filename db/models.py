"""
SQLAlchemy ORM 模型定義
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class News(Base):
    """新聞資料表 ORM 模型"""
    __tablename__ = 'news'
    
    pk = Column(Integer, primary_key=True, autoincrement=True, comment='主鍵，流水號')
    news_id = Column(String(100), nullable=False, comment='各新聞來源的原始ID')
    news_source = Column(String(50), nullable=False, comment='新聞來源 (SETN, LTN, TVBS, ChinaTimes)')
    author = Column(String(100), comment='作者/記者')
    title = Column(Text, comment='新聞標題')
    url = Column(Text, comment='新聞網址')
    publish_time = Column(String(50), comment='發布時間')
    create_time = Column(DateTime, default=func.now(), comment='資料建立時間')
    
    # 複合唯一約束：同一個新聞來源的同一個新聞ID不能重複
    __table_args__ = (
        UniqueConstraint('news_source', 'news_id', name='uq_news_source_id'),
    )
    
    def __repr__(self):
        return f'<News(pk={self.pk}, news_source={self.news_source}, news_id={self.news_id}, title={self.title[:50]})>'
    
    def to_dict(self):
        """轉換為字典格式"""
        return {
            'pk': self.pk,
            'news_id': self.news_id,
            'news_source': self.news_source,
            'author': self.author,
            'title': self.title,
            'url': self.url,
            'publish_time': self.publish_time,
            'create_time': self.create_time.isoformat() if self.create_time else None
        }

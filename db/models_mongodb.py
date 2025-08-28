"""
MongoDB 模型定義使用 MongoEngine
"""
from mongoengine import Document, StringField, DateTimeField
from datetime import datetime
from typing import Dict, Any


class News(Document):
    """新聞資料 MongoDB 模型"""
    
    # 使用 MongoEngine 欄位
    news_id = StringField(required=True, max_length=100, help_text='各新聞來源的原始ID')
    news_source = StringField(required=True, max_length=50, help_text='新聞來源 (SETN, LTN, TVBS, ChinaTimes)')
    author = StringField(max_length=100, help_text='作者/記者')
    title = StringField(help_text='新聞標題')
    url = StringField(help_text='新聞網址')
    publish_time = StringField(max_length=50, help_text='發布時間')
    create_time = DateTimeField(default=datetime.utcnow, help_text='資料建立時間')
    
    # 設定元數據
    meta = {
        'collection': 'news',  # 集合名稱
        'indexes': [
            'news_source',
            'news_id',
            'create_time',
            ('news_source', 'news_id'),  # 複合索引
        ],
        'index_background': True,
    }
    
    def __str__(self):
        return f'News(source={self.news_source}, id={self.news_id}, title={self.title[:50] if self.title else ""})'
    
    def __repr__(self):
        return f'<News(news_source={self.news_source}, news_id={self.news_id}, title={self.title[:50] if self.title else ""})>'
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            'pk': str(self.id),  # MongoDB ObjectId 轉為字串
            'news_id': self.news_id,
            'news_source': self.news_source,
            'author': self.author or '',
            'title': self.title or '',
            'url': self.url or '',
            'publish_time': self.publish_time or '',
            'create_time': self.create_time.isoformat() if self.create_time else None
        }
    
    @classmethod
    def exists(cls, news_source: str, news_id: str) -> bool:
        """檢查新聞是否已存在"""
        return cls.objects(news_source=news_source, news_id=news_id).first() is not None
    
    @classmethod
    def create_from_dict(cls, data: Dict[str, Any]) -> 'News':
        """從字典建立新聞物件"""
        return cls(
            news_id=data.get('news_id', ''),
            news_source=data.get('news_source', ''),
            author=data.get('author', ''),
            title=data.get('title', ''),
            url=data.get('url', ''),
            publish_time=data.get('publish_time', '')
        )

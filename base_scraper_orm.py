"""
使用 ORM 的新聞爬蟲基礎類別
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
import time
import random
from datetime import datetime
import logging

# 導入 ORM 資料庫管理
from news_orm_db import news_orm_db


class BaseNewsScraper(ABC):
    """新聞爬蟲的抽象基礎類別，使用 ORM 進行資料庫操作"""
    
    def __init__(self, base_url: str, news_source: str, max_retry: int = 3):
        """
        初始化爬蟲
        
        Args:
            base_url: 新聞網站的基本URL
            news_source: 新聞來源標識 (如 'SETN', 'LTN', 'TVBS', 'ChinaTimes')
            max_retry: 最大重試次數
        """
        self.base_url = base_url
        self.news_source = news_source
        self.max_retry = max_retry
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # 設定日誌
        self.logger = logging.getLogger(f"{news_source}Scraper")
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
        # 設定爬蟲延遲
        self.delay_range = (1, 3)
        
        # 初始化資料庫
        self.db = news_orm_db
    
    def _get_page_content(self, url: str) -> Optional[BeautifulSoup]:
        """
        獲取網頁內容
        
        Args:
            url: 目標URL
            
        Returns:
            BeautifulSoup: 解析後的網頁內容，失敗時返回 None
        """
        for attempt in range(self.max_retry):
            try:
                self.logger.info(f"正在獲取頁面: {url} (嘗試 {attempt + 1}/{self.max_retry})")
                
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                response.encoding = response.apparent_encoding
                
                return BeautifulSoup(response.text, 'html.parser')
                
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"獲取頁面失敗 (嘗試 {attempt + 1}/{self.max_retry}): {e}")
                if attempt < self.max_retry - 1:
                    time.sleep(2 ** attempt)  # 指數退避
                
        self.logger.error(f"無法獲取頁面內容: {url}")
        return None
    
    def _random_delay(self):
        """隨機延遲，避免對目標網站造成壓力"""
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)
    
    @abstractmethod
    def _get_news_list(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        從主頁面解析新聞列表
        
        Args:
            soup: 主頁面的 BeautifulSoup 物件
            
        Returns:
            List[Dict[str, str]]: 新聞列表，每項包含標題、URL等基本資訊
        """
        pass
    
    @abstractmethod
    def _get_news_detail(self, news_url: str) -> Optional[Dict[str, Any]]:
        """
        獲取新聞詳細內容
        
        Args:
            news_url: 新聞詳細頁面URL
            
        Returns:
            Dict[str, Any]: 新聞詳細資訊，失敗時返回 None
        """
        pass
    
    @abstractmethod
    def _extract_news_id(self, news_url: str) -> str:
        """
        從新聞URL中提取唯一ID
        
        Args:
            news_url: 新聞URL
            
        Returns:
            str: 新聞的唯一標識
        """
        pass
    
    def _convert_to_db_format(self, news_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        將爬取到的新聞資料轉換為資料庫格式
        子類別可以覆寫此方法來實現自定義轉換邏輯
        
        Args:
            news_data: 原始新聞資料
            
        Returns:
            Dict[str, Any]: 轉換後的資料庫格式資料
        """
        # 預設實現：直接返回原資料並加上 news_source
        db_data = news_data.copy()
        db_data['news_source'] = self.news_source
        
        # 確保包含必要欄位
        required_fields = ['news_id', 'title', 'url']
        for field in required_fields:
            if field not in db_data:
                self.logger.warning(f"缺少必要欄位 {field}")
                db_data[field] = ''
        
        # 設定預設值
        db_data.setdefault('author', '')
        db_data.setdefault('publish_time', '')
        
        return db_data
    
    def _save_news_to_db(self, news_data: Dict[str, Any]) -> bool:
        """
        將新聞資料儲存到資料庫
        
        Args:
            news_data: 新聞資料
            
        Returns:
            bool: 儲存成功返回 True，已存在返回 False
        """
        try:
            # 轉換為資料庫格式
            db_data = self._convert_to_db_format(news_data)
            
            # 使用 ORM 儲存
            return self.db.insert_news_item(db_data)
            
        except Exception as e:
            self.logger.error(f"儲存新聞到資料庫失敗: {e}")
            return False
    
    def _is_news_exists(self, news_id: str) -> bool:
        """
        檢查新聞是否已存在於資料庫中
        
        Args:
            news_id: 新聞ID
            
        Returns:
            bool: 存在返回 True，否則 False
        """
        return self.db.news_exists(self.news_source, news_id)
    
    def scrape_news(self, max_pages: int = 1, skip_existing: bool = True) -> Dict[str, int]:
        """
        執行新聞爬取 - 使用批量插入提高效率
        
        Args:
            max_pages: 最大爬取頁數
            skip_existing: 是否跳過已存在的新聞
            
        Returns:
            Dict[str, int]: 統計資訊 {'total': 總數, 'new': 新增數, 'skipped': 跳過數, 'failed': 失敗數}
        """
        stats = {'total': 0, 'new': 0, 'skipped': 0, 'failed': 0}
        collected_news = []  # 收集所有新聞資料，準備批量插入
        
        self.logger.info(f"開始爬取 {self.news_source} 新聞，最多 {max_pages} 頁")
        
        for page in range(1, max_pages + 1):
            try:
                self.logger.info(f"正在爬取第 {page} 頁")
                
                # 獲取新聞列表頁面
                page_url = self._get_page_url(page)
                soup = self._get_page_content(page_url)
                
                if not soup:
                    self.logger.error(f"無法獲取第 {page} 頁內容")
                    continue
                
                # 解析新聞列表
                news_list = self._get_news_list(soup)
                self.logger.info(f"第 {page} 頁找到 {len(news_list)} 條新聞")
                
                for news_item in news_list:
                    stats['total'] += 1
                    
                    try:
                        news_url = news_item.get('url', '')
                        if not news_url:
                            stats['failed'] += 1
                            continue
                        
                        # 提取新聞ID
                        news_id = self._extract_news_id(news_url)
                        
                        # 檢查是否已存在
                        if skip_existing and self._is_news_exists(news_id):
                            stats['skipped'] += 1
                            self.logger.debug(f"跳過已存在的新聞: {news_id}")
                            continue
                        
                        # 獲取新聞詳細內容
                        news_detail = self._get_news_detail(news_url)
                        if not news_detail:
                            stats['failed'] += 1
                            continue
                        
                        # 合併主頁面和詳細頁面的資料
                        merged_data = news_item.copy()  # 先複製主頁面資料
                        merged_data.update(news_detail)  # 再更新詳細頁面資料
                        
                        # 加上基本資訊
                        merged_data['news_id'] = news_id
                        merged_data['url'] = news_url
                        
                        # 轉換為資料庫格式並收集
                        db_data = self._convert_to_db_format(merged_data)
                        collected_news.append(db_data)
                        
                        self.logger.debug(f"收集新聞: {merged_data.get('title', 'Unknown')[:50]}")
                        
                        # 隨機延遲
                        self._random_delay()
                        
                    except Exception as e:
                        stats['failed'] += 1
                        self.logger.error(f"處理新聞時發生錯誤: {e}")
                
                # 頁面間延遲
                if page < max_pages:
                    self._random_delay()
                    
            except Exception as e:
                self.logger.error(f"爬取第 {page} 頁時發生錯誤: {e}")
        
        # 批量插入收集到的新聞
        if collected_news:
            self.logger.info(f"開始批量插入 {len(collected_news)} 條新聞到資料庫")
            try:
                inserted_count = self.db.insert_news_batch(collected_news)
                stats['new'] = inserted_count
                self.logger.info(f"批量插入完成 - 成功插入 {inserted_count} 條新聞")
            except Exception as e:
                self.logger.error(f"批量插入失敗: {e}")
                stats['failed'] += len(collected_news)
        
        self.logger.info(f"爬取完成 - 總計: {stats['total']}, 新增: {stats['new']}, 跳過: {stats['skipped']}, 失敗: {stats['failed']}")
        return stats
    
    def _get_page_url(self, page: int) -> str:
        """
        獲取指定頁面的URL
        預設實現返回 base_url，子類別可以覆寫此方法
        
        Args:
            page: 頁面編號
            
        Returns:
            str: 頁面URL
        """
        return self.base_url
    
    def get_scraped_count(self) -> int:
        """獲取已爬取的新聞數量"""
        total_count = self.db.get_news_count()
        source_counts = dict(self.db.get_news_count_by_source())
        return source_counts.get(self.news_source, 0)
    
    def cleanup(self):
        """清理資源"""
        if hasattr(self, 'session'):
            self.session.close()

"""
TVBS新聞爬蟲 - 使用ORM架構
基於舊版 tvbs/main.py 的邏輯改寫
"""

import sys
import os
import json
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# 添加根目錄到Python路徑
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from base_scraper_orm import BaseNewsScraper


class TVBSScraper(BaseNewsScraper):
    """TVBS新聞爬蟲 - 使用ORM版本，基於舊版API邏輯"""
    
    def __init__(self):
        super().__init__(
            base_url="https://news.tvbs.com.tw/politics",
            news_source="TVBS",
            max_retry=3
        )
        self.api_url = "https://news.tvbs.com.tw/news/get_breaking_news_other_cate"
        self.current_payload = None
    
    
    def _extract_payload_from_soup(self, soup: BeautifulSoup) -> Dict[str, str]:
        """從HTML中提取payload參數，基於舊版邏輯"""
        try:
            inputs = soup.select('div.container.politics input')
            payload = {}
            
            for input_element in inputs:
                if input_element.has_attr('value') and input_element.has_attr('id'):
                    payload[input_element['id']] = input_element['value']
            
            return payload
        except Exception as e:
            self.logger.error(f"提取payload失敗: {e}")
            return {}
    
    def _transform_payload(self, payload: Dict[str, str]) -> Dict[str, str]:
        """轉換payload格式，基於舊版邏輯"""
        return {
            'news_id': payload.get('last_news_id', ''),
            'page': payload.get('breaking_news_page', '2'),
            'date': payload.get('last_news_review_date', ''),
            'cate': payload.get('breaking_news_cate', '7'),
            'get_num': payload.get('breaking_news_get_num', '90')
        }
    
    def _get_news_list(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """從主頁面獲取新聞列表，基於舊版邏輯"""
        try:
            news_list = []
            
            # 1. 從主頁面提取新聞連結 (基於舊版的 get_newest_href 邏輯)
            links = soup.find_all('a', href=True)
            href_values = []
            
            for a in links:
                href = a.get('href')
                if href and isinstance(href, str) and "/politics/" in href:
                    href_values.append(href)
            
            for href in href_values:
                if href:
                    # 確保是完整URL
                    if not href.startswith('http'):
                        url = urljoin("https://news.tvbs.com.tw", href)
                    else:
                        url = href
                    
                    # 提取新聞ID
                    news_id = href.split('/')[-1] if '/' in href else href
                    
                    news_info = {
                        "title": "",  # 稍後從詳情頁獲取
                        "url": url,
                        "news_id": news_id,
                        "publish_time": ""
                    }
                    news_list.append(news_info)
            
            # 2. 提取payload用於API調用
            payload = self._extract_payload_from_soup(soup)
            self.current_payload = self._transform_payload(payload)
            
            return news_list
            
        except Exception as e:
            self.logger.error(f"解析新聞列表失敗: {e}")
            return []
    
    async def _get_additional_news_from_api(self) -> List[Dict[str, str]]:
        """使用API獲取更多新聞，基於舊版邏輯"""
        try:
            if not self.current_payload:
                return []
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, params=self.current_payload) as response:
                    if response.status == 200:
                        api_data = await response.json()
                        
                        if 'breaking_news_other' in api_data:
                            # 解析API返回的HTML
                            api_soup = BeautifulSoup(api_data['breaking_news_other'], 'html.parser')
                            
                            # 提取新聞連結
                            links = api_soup.find_all('a', href=True)
                            href_values = []
                            
                            for a in links:
                                href = a.get('href')
                                if href and isinstance(href, str) and "/politics/" in href:
                                    href_values.append(href)
                            
                            news_list = []
                            for href in href_values:
                                if href:
                                    if not href.startswith('http'):
                                        url = urljoin("https://news.tvbs.com.tw", href)
                                    else:
                                        url = href
                                    
                                    news_id = href.split('/')[-1] if '/' in href else href
                                    
                                    news_info = {
                                        "title": "",
                                        "url": url,
                                        "news_id": news_id,
                                        "publish_time": ""
                                    }
                                    news_list.append(news_info)
                            
                            return news_list
            
            return []
        except Exception as e:
            self.logger.error(f"API調用失敗: {e}")
            return []
    
    def _get_news_detail(self, news_url: str) -> Optional[Dict[str, Any]]:
        """獲取新聞詳細內容，基於舊版的 extract_details_from_html 邏輯"""
        soup = self._get_page_content(news_url)
        if not soup:
            return None
        
        try:
            # 檢查404錯誤
            if soup.find('div', class_='error_div'):
                self.logger.warning(f"404 錯誤: {news_url}")
                return None
            
            # 提取標題
            title_elem = soup.find('h1', class_='title')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # 提取作者和日期
            author = ""
            date_str = ""
            
            author_div = soup.find('div', class_='author')
            if author_div:
                # 提取作者
                if author_div.find('a'):
                    author = author_div.find('a').get_text(strip=True)
                
                # 提取發布時間
                for line in author_div.stripped_strings:
                    if "發佈時間：" in line:
                        date_str = line.replace("發佈時間：", "").strip()
            
            return {
                "title": title,
                "author": author,
                "publish_time": date_str
            }
            
        except Exception as e:
            self.logger.error(f"解析新聞詳情失敗: {e}")
            return None
    
    def _extract_news_id(self, news_url: str) -> str:
        """從URL提取新聞ID"""
        try:
            # TVBS URL格式: https://news.tvbs.com.tw/politics/1234567
            parts = news_url.split('/')
            if len(parts) > 0 and parts[-1].isdigit():
                return parts[-1]
            else:
                return str(hash(news_url))
        except:
            return str(hash(news_url))
    
    def _convert_to_db_format(self, news_data: Dict[str, Any]) -> Dict[str, Any]:
        """轉換為資料庫格式"""
        db_data = super()._convert_to_db_format(news_data)
        
        # 統一日期格式：將 YYYY/MM/DD 轉換為 YYYY-MM-DD HH:MM:SS
        if 'publish_time' in db_data:
            db_data['publish_time'] = self._normalize_date_format(db_data['publish_time'])
        
        return db_data
    
    def _normalize_date_format(self, date_str: str) -> str:
        """統一日期格式，基於舊版邏輯"""
        try:
            if not date_str:
                return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if '/' in date_str:
                # 處理 "2025/08/26 15:30" 格式
                date_str = date_str.replace('/', '-')
                
                # 如果沒有秒數，添加 :00
                if len(date_str.split(':')) == 2:
                    date_str += ':00'
                
                return date_str
            
            return date_str
        except Exception as e:
            self.logger.warning(f"日期格式化失敗: {date_str}, 錯誤: {e}")
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def test_tvbs_scraper():
    """測試TVBS爬蟲"""
    print("測試TVBS爬蟲 (ORM版本)")
    print("="*30)
    
    scraper = TVBSScraper()
    result = scraper.scrape_news(max_pages=1)  # 限制1頁做測試
    
    print("\n執行結果:")
    print(f"總計: {result['total']}")
    print(f"新增: {result['new']}")
    print(f"跳過: {result['skipped']}")
    print(f"失敗: {result['failed']}")


if __name__ == "__main__":
    test_tvbs_scraper()

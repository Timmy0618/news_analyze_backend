"""
TVBS新聞爬蟲 - 使用ORM架構
基於舊版 tvbs/main.py 的邏輯改寫
"""

import sys
import os
import json
import aiohttp
import asyncio
import pytz
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# 添加根目錄到Python路徑
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from .base_scraper_orm import BaseNewsScraper


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
        self.taipei_tz = pytz.timezone('Asia/Taipei')
        self.today = datetime.now(self.taipei_tz).date()  # 改為當天
    
    def is_today_news(self, date_str: str) -> bool:
        """檢查給定的日期字串是否為今天的新聞"""
        try:
            # 嘗試多種日期格式
            date_formats = [
                "%Y/%m/%d %H:%M",      # TVBS 新聞詳情頁格式: 2023/03/07 11:39
                "%Y-%m-%d %H:%M:%S",   # API 回傳格式: 2025-08-27 09:46:13
                "%Y/%m/%d %H:%M:%S"    # 有秒數的格式
            ]
            
            news_date = None
            for date_format in date_formats:
                try:
                    news_date = datetime.strptime(date_str, date_format)
                    break
                except ValueError:
                    continue
            
            if news_date is None:
                self.logger.warning(f"無法解析日期格式: {date_str}")
                return False
                
            # 只比較日期，不比較時間
            return news_date.date() == self.today
            
        except Exception as e:
            # 如果無法解析日期，回傳 False 以停止抓取
            self.logger.warning(f"日期檢查出錯: {date_str}, 錯誤: {e}")
            return False
    
    
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
    
    def _should_process_news(self, news_data: Dict[str, Any]) -> bool:
        """
        檢查是否應該處理這條新聞（TVBS 專用：只處理今天新聞）
        """
        publish_time = news_data.get('publish_time', '')
        if publish_time:
            return self.is_today_news(publish_time)
        return True  # 如果沒有時間資訊，預設處理

    def scrape_news(self, max_pages: int = 1, skip_existing: bool = True, 
                   max_consecutive_duplicates: int = 5) -> Dict[str, int]:
        """
        覆寫基類方法，加入時間檢查邏輯和連續重複檢查
        """
        self.logger.info(f"開始爬取 {self.news_source} 新聞，限制在今天 ({self.today}) 內")
        # 調用基類方法，基類已經包含連續重複檢查邏輯
        return super().scrape_news(max_pages, skip_existing, max_consecutive_duplicates)
        
        try:
            # 1. 首先獲取主頁面
            main_soup = self._get_page_content(self.base_url)
            if not main_soup:
                self.logger.error("無法獲取主頁面")
                return stats
            
            # 2. 提取初始新聞列表
            initial_news = self._get_news_list(main_soup)
            all_hrefs = set()
            
            # 收集初始新聞連結
            for news in initial_news:
                if news.get('url'):
                    href = news['url'].replace("https://news.tvbs.com.tw", "")
                    all_hrefs.add(href)
            
            # 3. 使用API獲取更多新聞（基於舊版邏輯）
            if self.current_payload:
                date_str = self.current_payload.get('date', '')
                
                # 使用 while 循環檢查時間，但改為檢查今天的新聞
                while self.is_today_news(date_str):
                    self.logger.info(f"正在獲取更多新聞，當前日期: {date_str}")
                    
                    try:
                        # 使用同步版本的 API 調用
                        response = self.session.get(self.api_url, params=self.current_payload)
                        if response.status_code == 200:
                            api_data = response.json()
                            
                            if 'breaking_news_other' in api_data:
                                # 解析新聞連結
                                api_soup = BeautifulSoup(api_data['breaking_news_other'], 'html.parser')
                                links = api_soup.find_all('a', href=True)
                                
                                for a in links:
                                    href = a.get('href')
                                    if href and isinstance(href, str) and "/politics/" in href:
                                        all_hrefs.add(href)
                                
                                # 更新 payload（基於舊版邏輯）
                                if 'last_news_id' in api_data:
                                    self.current_payload['news_id'] = api_data['last_news_id']
                                if 'last_news_review_date' in api_data:
                                    date_str = api_data['last_news_review_date']
                                    self.current_payload['date'] = date_str
                                if 'page' in api_data:
                                    self.current_payload['page'] = str(int(api_data['page']) + 1)
                            else:
                                self.logger.info("API 沒有更多新聞")
                                break
                        else:
                            self.logger.error(f"API 請求失敗: {response.status_code}")
                            break
                            
                        # 避免請求過於頻繁
                        self._random_delay()
                        
                    except Exception as e:
                        self.logger.error(f"API 請求失敗: {e}")
                        break
            
            self.logger.info(f"總共收集到 {len(all_hrefs)} 個新聞連結")
            
            # 4. 處理所有收集到的新聞連結
            for href in all_hrefs:
                stats['total'] += 1
                
                try:
                    news_url = f"https://news.tvbs.com.tw{href}"
                    news_id = self._extract_news_id(news_url)
                    
                    # 檢查是否已存在
                    if skip_existing and self._is_news_exists(news_id):
                        stats['skipped'] += 1
                        continue
                    
                    # 獲取新聞詳情
                    news_detail = self._get_news_detail(news_url)
                    if not news_detail:
                        stats['failed'] += 1
                        continue
                    
                    # 檢查新聞發布時間是否為今天（就像其他爬蟲一樣）
                    publish_time_str = news_detail.get('publish_time', '')
                    if publish_time_str and not self.is_today_news(publish_time_str):
                        self.logger.info(f"新聞時間不是今天，跳過: {publish_time_str}")
                        stats['skipped'] += 1
                        continue
                    
                    # 準備新聞資料
                    merged_data = {
                        'url': news_url,
                        'news_id': news_id,
                        'source': self.news_source,
                        **news_detail
                    }
                    
                    # 轉換為資料庫格式
                    db_data = self._convert_to_db_format(merged_data)
                    collected_news.append(db_data)
                    
                    self.logger.info(f"收集新聞: {news_detail.get('title', 'Unknown')[:50]}")
                    
                    # 隨機延遲
                    self._random_delay()
                    
                except Exception as e:
                    stats['failed'] += 1
                    self.logger.error(f"處理新聞時發生錯誤: {e}")
            
            # 5. 批量插入收集到的新聞
            if collected_news:
                self.logger.info(f"開始批量插入 {len(collected_news)} 條新聞到資料庫")
                try:
                    inserted_count = self.db.insert_news_batch(collected_news)
                    stats['new'] = inserted_count
                    self.logger.info(f"批量插入完成 - 成功插入 {inserted_count} 條新聞")
                except Exception as e:
                    self.logger.error(f"批量插入失敗: {e}")
                    stats['failed'] += len(collected_news)
            
        except Exception as e:
            self.logger.error(f"爬取過程中發生錯誤: {e}")
        
        self.logger.info(f"爬取完成 - 總計: {stats['total']}, 新增: {stats['new']}, 跳過: {stats['skipped']}, 失敗: {stats['failed']}")
        return stats


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

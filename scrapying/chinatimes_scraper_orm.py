"""
ChinaTimes新聞爬蟲 - 使用ORM架構
"""

import sys
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# 添加根目錄到Python路徑
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from .base_scraper_orm import BaseNewsScraper


class ChinaTimesScraper(BaseNewsScraper):
    """中國時報新聞爬蟲 - 使用ORM版本"""
    
    def __init__(self):
        super().__init__(
            base_url="https://www.chinatimes.com/politic/?chdtv",
            news_source="ChinaTimes",
            max_retry=3
        )
    
    def _get_news_list(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """從主頁面解析新聞列表"""
        news_list = []
        
        try:
            # 查找新聞項目
            news_items = soup.select('h3.title a, .articletitle a')
            
            for item in news_items:
                try:
                    title = item.get_text(strip=True)
                    url = item.get('href')
                    
                    if url:
                        # 處理相對URL
                        if not url.startswith('http'):
                            url = urljoin("https://www.chinatimes.com", url)
                        
                        # 只處理包含時間戳的新聞URL
                        if self._is_valid_news_url(url):
                            news_info = {
                                "title": title,
                                "url": url,
                                "publish_time": ""  # 將在詳細頁面中獲取
                            }
                            news_list.append(news_info)
                        
                except Exception as e:
                    self.logger.error(f"解析新聞項目失敗: {e}")
                    continue
            
            return news_list
            
        except Exception as e:
            self.logger.error(f"解析新聞列表失敗: {e}")
            return []
    
    def _get_news_detail(self, news_url: str) -> Optional[Dict[str, Any]]:
        """獲取新聞詳細內容"""
        soup = self._get_page_content(news_url)
        if not soup:
            return None
        
        try:
            # 提取作者信息
            author = self._extract_author(soup)
            
            # 提取發布時間
            publish_time = self._extract_publish_time(soup)
            
            # 提取標題（如果主頁面沒有獲取到）
            title_elem = soup.select_one('h1.article-title, .articletitle h1')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            return {
                "author": author or "",
                "publish_time": publish_time or "",
                "title": title
            }
            
        except Exception as e:
            self.logger.error(f"解析新聞詳情失敗: {e}")
            return None
    
    def _extract_news_id(self, news_url: str) -> str:
        """從URL提取新聞ID"""
        try:
            # ChinaTimes URL通常包含時間戳
            # 例如: https://www.chinatimes.com/newspapers/20231227000123-260102
            if '/newspapers/' in news_url or '/realtimenews/' in news_url:
                # 提取時間戳部分作為ID
                parts = news_url.split('/')
                for part in parts:
                    if part and (part.startswith('20') or '-' in part):
                        # 移除可能的查詢參數
                        clean_id = part.split('?')[0].split('#')[0]
                        return clean_id
            
            return str(hash(news_url))
        except:
            return str(hash(news_url))
    
    def _convert_to_db_format(self, news_data: Dict[str, Any]) -> Dict[str, Any]:
        """轉換為資料庫格式"""
        db_data = super()._convert_to_db_format(news_data)
        
        # 統一日期格式：將 YYYY/MM/DD 轉換為 YYYY-MM-DD  
        if 'publish_time' in db_data:
            db_data['publish_time'] = self._normalize_date_format(db_data['publish_time'])
        
        return db_data
    
    def _normalize_date_format(self, date_str: str) -> str:
        """統一日期格式，處理 ChinaTimes 的各種時間格式"""
        try:
            if not date_str:
                return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 處理 ISO 8601 格式 (2025-08-27T11:45:34+08:00)
            if 'T' in date_str and '+' in date_str:
                # 解析 ISO 格式
                dt = datetime.fromisoformat(date_str.replace('+08:00', ''))
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # 處理 datetime 屬性格式 (2025-08-27 11:45)
            if '-' in date_str and ':' in date_str and len(date_str.split()) == 2:
                date_part, time_part = date_str.split()
                if len(time_part.split(':')) == 2:
                    return f"{date_part} {time_part}:00"
                return date_str
            
            # 處理舊格式 (2025/08/27)
            if '/' in date_str:
                normalized = date_str.replace('/', '-')
                # 如果只有日期，添加當前時間
                if ':' not in normalized:
                    current_time = datetime.now().strftime('%H:%M:%S')
                    return f"{normalized} {current_time}"
                return normalized
            
            # 處理混合格式 (11:452025/08/27)
            import re
            match = re.match(r'(\d{2}:\d{2})(\d{4}/\d{2}/\d{2})', date_str)
            if match:
                time_part = match.group(1)
                date_part = match.group(2).replace('/', '-')
                return f"{date_part} {time_part}:00"
            
            return date_str
        except Exception as e:
            self.logger.warning(f"日期格式化失敗: {date_str}, 錯誤: {e}")
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def _is_valid_news_url(self, url: str) -> bool:
        """檢查是否為有效的新聞URL"""
        try:
            # 檢查是否包含新聞路徑和時間戳
            valid_paths = ['/newspapers/', '/realtimenews/', '/politic/']
            return any(path in url for path in valid_paths)
        except:
            return False
    
    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """提取作者信息"""
        try:
            # 尋找作者相關標籤
            author_selectors = [
                '.author',
                '.reporter',
                '[class*="author"]',
                '.article-author',
                '.byline'
            ]
            
            for selector in author_selectors:
                author_elem = soup.select_one(selector)
                if author_elem:
                    author_text = author_elem.get_text(strip=True)
                    # 清理作者文字
                    if author_text:
                        return self._clean_author_text(author_text)
            
            return None
        except Exception as e:
            self.logger.error(f"提取作者失敗: {e}")
            return None
    
    def _clean_author_text(self, author_text: str) -> str:
        """清理作者文字"""
        try:
            # 移除常見的前綴和後綴
            cleaned = author_text
            
            # 移除時間信息
            cleaned = re.sub(r'\d{4}/\d{1,2}/\d{1,2}.*', '', cleaned)
            cleaned = re.sub(r'\d{2}:\d{2}.*', '', cleaned)
            
            # 提取記者姓名
            if '記者' in cleaned:
                match = re.search(r'記者([^／\s\n]+)', cleaned)
                if match:
                    return match.group(1).strip()
            
            return cleaned.strip()
        except:
            return author_text
    
    def _extract_publish_time(self, soup: BeautifulSoup) -> Optional[str]:
        """提取發布時間"""
        try:
            # 1. 優先從time標籤的datetime屬性獲取
            time_elem = soup.select_one('time[datetime]')
            if time_elem:
                datetime_str = time_elem.get('datetime')
                if datetime_str and isinstance(datetime_str, str):
                    return self._normalize_date_format(datetime_str)
            
            # 2. 從meta標籤獲取發布時間
            meta_published = soup.select_one('meta[property="article:published_time"]')
            if meta_published:
                content = meta_published.get('content')
                if content and isinstance(content, str):
                    return self._normalize_date_format(content)
            
            # 3. 從time標籤文字內容提取（作為備選）
            time_elem = soup.select_one('time')
            if time_elem:
                time_text = time_elem.get_text(strip=True)
                if time_text:
                    return self._normalize_date_format(time_text)
            
            return None
        except Exception as e:
            self.logger.error(f"提取發布時間失敗: {e}")
            return None


def test_chinatimes_scraper():
    """測試中國時報爬蟲"""
    print("測試中國時報爬蟲 (ORM版本)")
    print("="*30)
    
    scraper = ChinaTimesScraper()
    result = scraper.scrape_news(max_pages=1)  # 限制1頁做測試
    
    print("\n執行結果:")
    print(f"總計: {result['total']}")
    print(f"新增: {result['new']}")
    print(f"跳過: {result['skipped']}")
    print(f"失敗: {result['failed']}")


if __name__ == "__main__":
    test_chinatimes_scraper()

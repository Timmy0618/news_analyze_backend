"""
SETN新聞爬蟲 - 使用ORM架構
"""

import sys
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

# 添加根目錄到Python路徑
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from base_scraper_orm import BaseNewsScraper


"""
SETN新聞爬蟲 - 使用ORM架構
"""

import sys
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

# 添加根目錄到Python路徑
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from base_scraper_orm import BaseNewsScraper


class SETNScraper(BaseNewsScraper):
    """SETN新聞爬蟲 - 使用ORM版本"""
    
    def __init__(self):
        super().__init__(
            base_url="https://www.setn.com/ViewAll.aspx?PageGroupID=6",
            news_source="SETN",
            max_retry=3
        )
        self.current_year = datetime.now().year
    
    def _get_page_url(self, page: int) -> str:
        """獲取指定頁面的URL"""
        return f"https://www.setn.com/ViewAll.aspx?PageGroupID=6&p={page}"
    
    def _get_news_list(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """從主頁面解析新聞列表"""
        news_list = []
        
        try:
            # 尋找新聞項目
            for item in soup.find_all('div', class_='col-sm-12 newsItems'):
                try:
                    link_tag = item.find('a', href=True, class_='gt')
                    time_tag = item.find('time')
                    
                    if link_tag and time_tag:
                        title = link_tag.get_text(strip=True)
                        relative_url = link_tag['href']
                        
                        # 建構完整URL
                        full_url = urljoin("https://www.setn.com/", relative_url)
                        
                        # 清理URL，只保留NewsID參數
                        cleaned_url = self._clean_url(full_url)
                        
                        # 處理時間格式
                        time_text = time_tag.get_text(strip=True)
                        
                        news_info = {
                            "title": title,
                            "url": cleaned_url,
                            "publish_time": time_text
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
            # 提取作者資訊（從第一個p標籤）
            author = self._extract_author(soup)
            
            # 從詳細頁面提取標題（作為備用）
            title_elem = soup.select_one('h1.news-title-3, .news-title, h1')
            detail_title = title_elem.get_text(strip=True) if title_elem else ""
            
            # 提取發布時間（從新聞內容頁面）
            publish_time = self._extract_detail_publish_time(soup)
            
            return {
                "author": author or "",
                "detail_title": detail_title,  # 用不同的key避免覆蓋主頁面標題
                "detail_publish_time": publish_time or ""
            }
            
        except Exception as e:
            self.logger.error(f"解析新聞詳情失敗: {e}")
            return None
    
    def _convert_to_db_format(self, news_data: Dict[str, Any]) -> Dict[str, Any]:
        """轉換為資料庫格式，正確合併主頁面和詳細頁面資料"""
        # 先調用父類方法設定基本格式
        db_data = super()._convert_to_db_format(news_data)
        
        # 確保標題不為空（優先使用主頁面標題，詳細頁面標題作備用）
        if 'title' not in db_data or not db_data.get('title'):
            if 'detail_title' in news_data and news_data['detail_title']:
                db_data['title'] = news_data['detail_title']
        
        # 處理發布時間（主頁面的時間格式需要補完）
        if 'publish_time' in db_data and db_data['publish_time']:
            # 主頁面時間格式如 "08/27 14:02"，需要加上年份
            db_data['publish_time'] = self._normalize_date_format(db_data['publish_time'])
        elif 'detail_publish_time' in news_data and news_data['detail_publish_time']:
            # 使用詳細頁面的時間作為備用
            db_data['publish_time'] = news_data['detail_publish_time']
        
        return db_data
    
    def _extract_news_id(self, news_url: str) -> str:
        """從URL提取新聞ID"""
        try:
            if 'NewsID=' in news_url:
                return news_url.split('NewsID=')[-1]
            else:
                return str(hash(news_url))
        except:
            return str(hash(news_url))
    
    def _normalize_date_format(self, date_str: str) -> str:
        """統一日期格式"""
        try:
            # SETN的時間格式通常是 "12/25 15:30" 這樣的格式
            if '/' in date_str and ':' in date_str:
                # 加上當前年份
                if date_str.count('/') == 1:  # MM/DD HH:MM 格式
                    full_time = f"{self.current_year}/{date_str}"
                    dt = datetime.strptime(full_time, '%Y/%m/%d %H:%M')
                    return dt.strftime('%Y-%m-%d %H:%M:%S')
                elif date_str.count('/') == 2:  # YYYY/MM/DD HH:MM 格式
                    # 替換 / 為 -
                    return date_str.replace('/', '-')
            
            return date_str
        except Exception as e:
            self.logger.warning(f"日期格式化失敗: {date_str}, 錯誤: {e}")
            return date_str
    
    def _clean_url(self, url: str) -> str:
        """清理URL，只保留NewsID參數"""
        try:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            news_id = query_params.get('NewsID')
            if news_id:
                return f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?NewsID={news_id[0]}"
            return url
        except:
            return url
    
    def _extract_detail_publish_time(self, soup: BeautifulSoup) -> Optional[str]:
        """從詳細頁面提取發布時間"""
        try:
            # 尋找時間相關標籤
            time_selectors = [
                'time.news-flash-date',
                'time[datetime]',
                '.publish-time',
                '.news-time'
            ]
            
            for selector in time_selectors:
                time_elem = soup.select_one(selector)
                if time_elem:
                    time_text = time_elem.get_text(strip=True)
                    if time_text:
                        return self._normalize_date_format(time_text)
            
            return None
        except Exception as e:
            self.logger.error(f"提取詳細頁面時間失敗: {e}")
            return None
    
    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """提取作者資訊"""
        try:
            # 尋找包含記者資訊的div
            author_div = soup.find("div", id="ckuse", attrs={"itemprop": "articleBody"})
            if author_div:
                # 找第一個p標籤
                paragraphs = author_div.find_all("p")
                if paragraphs:
                    author_text = paragraphs[0].get_text(strip=True)
                    if author_text:
                        return self._extract_author_from_text(author_text)
            
            return None
            
        except Exception as e:
            self.logger.error(f"提取作者失敗: {e}")
            return None
    
    def _extract_author_from_text(self, text: str) -> Optional[str]:
        """從文字中提取作者名稱"""
        patterns = [
            re.compile(r'記者(\S+)／\S+報導'),    # "記者陳怡潔／台北報導"
            re.compile(r'政治中心／(\S+)報導'),     # "政治中心／張家寧報導"
            re.compile(r'文、圖／(\S+)'),         # "文、圖／鏡週刊"
            re.compile(r'圖、文／(\S+)'),         # "圖、文／鏡週刊"
            re.compile(r'文／(\S+)'),            # "文／記者名"
            re.compile(r'文／\S+／(\S+)'),        # "文／住展雜誌／陳曼羚"
        ]
        
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                return match.group(1)
        
        return None


def test_setn_scraper():
    """測試SETN爬蟲"""
    print("測試SETN爬蟲 (ORM版本)")
    print("="*30)
    
    scraper = SETNScraper()
    result = scraper.scrape_news(max_pages=1)  # 限制1頁做測試
    
    print("\n執行結果:")
    print(f"總計: {result['total']}")
    print(f"新增: {result['new']}")
    print(f"跳過: {result['skipped']}")
    print(f"失敗: {result['failed']}")


if __name__ == "__main__":
    test_setn_scraper()

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

from .base_scraper_orm import BaseNewsScraper


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
    
    def scrape_news(self, max_pages: int = 1, skip_existing: bool = True, 
                   max_consecutive_duplicates: int = 5) -> Dict[str, int]:
        """
        執行新聞爬取 - SETN 專用，只抓取當天新聞，支持連續重複檢查
        
        Args:
            max_pages: 最大爬取頁數
            skip_existing: 是否跳過已存在的新聞
            max_consecutive_duplicates: 最大連續重複新聞數量，超過時停止爬取
            
        Returns:
            Dict[str, int]: 統計資訊 {'total': 總數, 'new': 新增數, 'skipped': 跳過數, 'failed': 失敗數}
        """
        stats = {'total': 0, 'new': 0, 'skipped': 0, 'failed': 0}
        collected_news = []  # 收集所有新聞資料，準備批量插入
        consecutive_duplicates = 0  # 連續重複計數器
        
        self.logger.info(f"開始爬取 {self.news_source} 新聞（只抓取當天），最多 {max_pages} 頁，最大連續重複: {max_consecutive_duplicates}")
        
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
                
                if not news_list:
                    self.logger.warning(f"第 {page} 頁沒有找到新聞")
                    break
                
                page_new_news = 0  # 當前頁面新增的新聞數
                
                # 處理每條新聞
                for news_item in news_list:
                    try:
                        stats['total'] += 1
                        
                        # 先檢查時間是否為當天（SETN 特殊邏輯）
                        if not self._should_process_news(news_item):
                            stats['skipped'] += 1
                            continue
                        
                        news_url = news_item.get('url', '')
                        if not news_url:
                            stats['failed'] += 1
                            continue
                        
                        # 提取新聞ID
                        news_id = self._extract_news_id(news_url)
                        
                        # 檢查是否已存在
                        if skip_existing and self._is_news_exists(news_id):
                            stats['skipped'] += 1
                            consecutive_duplicates += 1
                            self.logger.debug(f"跳過已存在的新聞: {news_id} (連續重複: {consecutive_duplicates})")
                            
                            # 檢查是否超過連續重複限制
                            if consecutive_duplicates >= max_consecutive_duplicates:
                                self.logger.info(f"連續 {consecutive_duplicates} 條重複新聞，停止爬取")
                                return self._finalize_scraping(stats, collected_news)
                            
                            continue
                        
                        # 重置連續重複計數器（找到新新聞）
                        consecutive_duplicates = 0
                        
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
                        
                        # 再次檢查處理後的時間（雙重保險）
                        if not self._should_process_news(merged_data):
                            stats['skipped'] += 1
                            continue
                        
                        # 轉換為資料庫格式並收集
                        db_data = self._convert_to_db_format(merged_data)
                        collected_news.append(db_data)
                        page_new_news += 1
                        
                        self.logger.debug(f"收集新聞: {merged_data.get('title', 'Unknown')[:50]}")
                        
                        # 隨機延遲
                        self._random_delay()
                        
                    except Exception as e:
                        stats['failed'] += 1
                        self.logger.error(f"處理新聞時發生錯誤: {e}")
                
                # 頁面統計日誌
                if page_new_news > 0:
                    self.logger.info(f"第 {page} 頁新增 {page_new_news} 條新新聞")
                else:
                    self.logger.info(f"第 {page} 頁沒有新增新聞")
                
            except Exception as e:
                self.logger.error(f"處理第 {page} 頁時發生錯誤: {e}")
                continue
        
        return self._finalize_scraping(stats, collected_news)

    def _should_process_news(self, news_data: Dict[str, Any]) -> bool:
        """
        檢查是否應該處理這條新聞（SETN 專用：只處理當天新聞）
        
        Args:
            news_data: 新聞資料
            
        Returns:
            bool: True 表示處理，False 表示跳過
        """
        # 檢查是否是當天新聞（SETN 專用邏輯）
        if 'publish_time' in news_data:
            normalized_time = self._normalize_date_format(news_data['publish_time'])
            if not self._is_today_news(normalized_time):
                self.logger.debug(f"跳過非當天新聞: {news_data.get('title', 'Unknown')} - {normalized_time}")
                return False
        
        return True

    def _is_today_news(self, publish_time_str: str) -> bool:
        """檢查新聞是否是當天的新聞"""
        try:
            # 解析發布時間
            if isinstance(publish_time_str, str):
                # 嘗試解析標準格式 YYYY-MM-DD HH:MM:SS
                if len(publish_time_str) >= 10:
                    news_date = datetime.strptime(publish_time_str[:10], '%Y-%m-%d').date()
                    today = datetime.now().date()
                    return news_date == today
            return False
        except Exception as e:
            self.logger.debug(f"檢查日期失敗: {publish_time_str}, 錯誤: {e}")
            return False

    def _normalize_date_format(self, date_str: str) -> str:
        """統一日期格式，智能處理跨年問題"""
        try:
            # SETN的時間格式通常是 "12/25 15:30" 這樣的格式
            if '/' in date_str and ':' in date_str:
                # 加上當前年份
                if date_str.count('/') == 1:  # MM/DD HH:MM 格式
                    full_time = f"{self.current_year}/{date_str}"
                    dt = datetime.strptime(full_time, '%Y/%m/%d %H:%M')
                    
                    # 檢查是否是未來日期（超過當天）
                    now = datetime.now()
                    # 如果解析出的日期大於現在時間超過 1 天，可能是去年的新聞
                    if dt > now and (dt - now).days > 0:
                        # 嘗試使用上一年
                        try:
                            prev_year = self.current_year - 1
                            full_time_prev = f"{prev_year}/{date_str}"
                            dt_prev = datetime.strptime(full_time_prev, '%Y/%m/%d %H:%M')
                            self.logger.debug(f"日期 {date_str} 可能是未來日期，調整為去年: {dt_prev}")
                            return dt_prev.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            # 如果失敗，還是用原來的邏輯
                            pass
                    
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

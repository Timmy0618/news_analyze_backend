"""
LTN新聞爬蟲 - 使用ORM架構
"""

import sys
import os
import json
import re
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

# 添加根目錄到Python路徑
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from .base_scraper_orm import BaseNewsScraper


class LTNScraper(BaseNewsScraper):
    """LTN新聞爬蟲 - 使用ORM版本"""
    
    def __init__(self):
        super().__init__(
            base_url="https://news.ltn.com.tw/ajax/breakingnews/politics/1",
            news_source="LTN",
            max_retry=3
        )
    
    def _get_page_url(self, page: int) -> str:
        """獲取指定頁面的URL"""
        return f"https://news.ltn.com.tw/ajax/breakingnews/politics/{page}"
    
    def _get_news_list(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """從主頁面解析新聞列表 (LTN返回JSON格式)"""
        try:
            # LTN API 返回JSON格式，soup.get_text()獲取原始文本
            json_text = soup.get_text()
            data = json.loads(json_text)
            
            if not data or "data" not in data:
                return []
            
            news_data = data["data"]
            if isinstance(news_data, dict):
                news_data = news_data.values()
            
            news_list = []
            for news_item in news_data:
                try:
                    news_info = {
                        "title": news_item['title'],
                        "url": news_item['url'],
                        "publish_time": news_item['time']
                    }
                    news_list.append(news_info)
                except Exception as e:
                    self.logger.error(f"處理新聞項目失敗: {e}")
                    continue
            
            return news_list
            
        except Exception as e:
            self.logger.error(f"解析新聞列表失敗: {e}")
            return []
    
    def _get_news_detail(self, news_url: str) -> Optional[Dict[str, Any]]:
        """獲取新聞詳細內容"""
        try:
            author = None
            
            # 根據URL類型選擇不同的提取方法
            if '/paper/' in news_url:
                # 處理報紙版文章 (paper類型)
                author = self._extract_reporter_from_paper(news_url)
            elif '/breakingnews/' in news_url:
                # 處理即時新聞文章 (breakingnews類型)
                # 先嘗試API方法
                author = self._extract_reporter_names(news_url)
                # 如果API方法失敗，回退到通用方法
                if not author:
                    author = self._extract_reporter_from_general(news_url)
            else:
                # 通用處理方法
                author = self._extract_reporter_from_general(news_url)
            
            return {
                "author": author or ""
            }
            
        except Exception as e:
            self.logger.error(f"解析新聞詳情失敗: {e}")
            return None
    
    def _extract_news_id(self, news_url: str) -> str:
        """從URL提取新聞ID"""
        try:
            # LTN URL格式: https://news.ltn.com.tw/news/politics/breakingnews/1234567
            if 'breakingnews/' in news_url:
                return news_url.split('breakingnews/')[-1]
            else:
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
        """統一日期格式"""
        try:
            # 處理LTN的時間格式
            if ':' in date_str and len(date_str) <= 6:  # 格式如 "13:53"
                # 只有時間沒有日期，添加今天的日期
                today_date = datetime.now().strftime("%Y-%m-%d")
                return f"{today_date} {date_str}:00"  # 添加秒數
            elif '/' in date_str:
                # 替換 / 為 -
                normalized = date_str.replace('/', '-')
                
                # 如果只有時間沒有日期，添加今天的日期  
                if ' ' not in normalized:
                    today_date = datetime.now().strftime("%Y-%m-%d")
                    normalized = f"{today_date} {normalized}"
                elif normalized.count('-') == 1:  # MM-DD HH:MM 格式
                    current_year = datetime.now().year
                    normalized = f"{current_year}-{normalized}"
                
                return normalized
            
            return date_str
        except Exception as e:
            self.logger.warning(f"日期格式化失敗: {date_str}, 錯誤: {e}")
            return date_str
    
    def _extract_reporter_names(self, news_url: str) -> Optional[str]:
        """從LTN API提取記者資訊"""
        try:
            # 從URL提取news_id
            news_id = self._extract_news_id(news_url)
            
            # 使用LTN的articleAjax API - 直接用requests而非BeautifulSoup
            api_url = f"https://news.ltn.com.tw/articleAjax/breakingnews/{news_id}/2"
            
            response = self.session.get(api_url, timeout=10)
            
            if response.status_code != 200:
                self.logger.warning(f"API請求失敗 ({news_id}): HTTP {response.status_code}")
                return None
            
            # 直接從response.text解析JSON，避免BeautifulSoup可能的編碼問題
            try:
                data = response.json()  # 使用response.json()方法
            except Exception as json_err:
                self.logger.error(f"JSON解析失敗 ({news_id}): {json_err}")
                # 嘗試手動處理一些常見的JSON問題
                try:
                    # 嘗試清理常見的問題字符
                    clean_text = response.text.replace('\\n', '\\\\n').replace('\\r', '\\\\r')
                    data = json.loads(clean_text)
                except:
                    self.logger.debug(f"回應內容前200字符: {response.text[:200]}")
                    return None
            
            if data and "A_Html" in data:
                html_content = data["A_Html"]
                return self._extract_reporter_names_from_html(html_content)
            
            return None
            
        except Exception as e:
            self.logger.error(f"提取記者資訊失敗: {e}")
            return None

    def _extract_reporter_names_from_html(self, html_content: str) -> Optional[str]:
        """從HTML內容中提取記者名稱"""
        try:
            # 使用多種正則表達式模式提取記者資訊，包含更多格式
            patterns = [
                r"〔記者(.*?)／(.*?)報導〕",   # 〔記者XXX／地點報導〕
                r"〔記者(.*?)／",             # 〔記者XXX／
                r"記者(.*?)／(.*?)報導",       # 記者XXX／地點報導
                r"記者(.*?)／",               # 記者XXX／
                r"記者(.*?)攝",               # 記者XXX攝
                r"(.*?)攝\）",                # XXX攝）
                r"(.*?)攝",                   # XXX攝
                r"採訪(.*?)／",               # 採訪XXX／
                r"撰稿(.*?)／",               # 撰稿XXX／
                r"編譯(.*?)／",               # 編譯XXX／
                r"綜合報導\/(.*?)報導",       # 綜合報導/XXX報導
                r"文\/(.*?)記者",             # 文/XXX記者
                r"文\/(.*?)\s",               # 文/XXX（空格結尾）
            ]
            
            all_matches = []
            for pattern in patterns:
                matches = re.findall(pattern, html_content)
                if matches:
                    # 處理包含元組的匹配結果
                    for match in matches:
                        if isinstance(match, tuple):
                            # 對於元組，取第一個元素（記者姓名）
                            all_matches.append(match[0])
                        else:
                            all_matches.append(match)
            
            if all_matches:
                # 分割名字並去重和清理
                names = set()
                for match in all_matches:
                    # 處理多個記者名稱（用「、」分隔）
                    for name in match.split("、"):
                        clean_name = name.strip()
                        # 去除常見的後綴（攝影、攝、報導等）和括弧
                        clean_name = re.sub(r'[攝影、攝報導）\)]+.*$', '', clean_name)
                        clean_name = re.sub(r'\(.*?\)', '', clean_name)  # 去除括弧內容
                        clean_name = clean_name.strip()
                        
                        # 只保留中文姓名（2-4個字符）
                        if re.match(r'^[\u4e00-\u9fff]{2,4}$', clean_name):
                            names.add(clean_name)
                
                if names:
                    return ', '.join(sorted(names))  # 排序保持一致性
            
            # 如果上述模式都沒有找到，嘗試更寬泛的搜索
            # 尋找以記者開頭的段落
            lines = html_content.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('〔記者') or line.startswith('記者'):
                    # 清理HTML標籤
                    clean_line = re.sub(r'<[^>]+>', '', line)
                    # 使用基本模式提取
                    basic_patterns = [
                        r'〔記者([^／]+)',
                        r'記者([^／]+)'
                    ]
                    for pattern in basic_patterns:
                        match = re.search(pattern, clean_line)
                        if match:
                            name = match.group(1).strip()
                            if re.match(r'^[\u4e00-\u9fff]{2,4}$', name):
                                return name
            
            return None
            
        except Exception as e:
            self.logger.error(f"從HTML提取記者名稱失敗: {e}")
            return None

    def _extract_reporter_from_paper(self, news_url: str) -> Optional[str]:
        """從LTN報紙版文章中提取記者資訊"""
        try:
            response = self.session.get(news_url, timeout=10)
            if response.status_code != 200:
                self.logger.warning(f"無法獲取頁面內容: {news_url}")
                return None
            
            html_content = response.text
            return self._extract_reporter_names_from_html(html_content)
            
        except Exception as e:
            self.logger.error(f"從報紙版提取記者資訊失敗: {e}")
            return None

    def _extract_reporter_from_general(self, news_url: str) -> Optional[str]:
        """從一般LTN文章中提取記者資訊（通用方法）"""
        try:
            response = self.session.get(news_url, timeout=10)
            if response.status_code != 200:
                self.logger.warning(f"無法獲取頁面內容: {news_url}")
                return None
            
            html_content = response.text
            
            # 方法1: 從HTML內容直接提取
            author = self._extract_reporter_names_from_html(html_content)
            if author:
                return author
            
            # 方法2: 從JSON-LD結構化資料中提取
            author = self._extract_reporter_from_json_ld(html_content)
            if author:
                return author
            
            # 方法3: 從meta標籤中提取
            author = self._extract_reporter_from_meta(html_content)
            if author:
                return author
                
            return None
            
        except Exception as e:
            self.logger.error(f"從一般文章提取記者資訊失敗: {e}")
            return None

    def _extract_reporter_from_json_ld(self, html_content: str) -> Optional[str]:
        """從JSON-LD結構化資料中提取記者資訊"""
        try:
            import json
            import re
            
            # 尋找JSON-LD標籤
            json_ld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
            json_matches = re.findall(json_ld_pattern, html_content, re.DOTALL | re.IGNORECASE)
            
            for json_text in json_matches:
                try:
                    data = json.loads(json_text.strip())
                    
                    # 檢查不同的JSON-LD欄位
                    text_fields = []
                    
                    # 常見的欄位名稱
                    if isinstance(data, dict):
                        for field in ['description', 'articleBody', 'text', 'headline']:
                            if field in data and isinstance(data[field], str):
                                text_fields.append(data[field])
                    
                    # 從這些文字欄位中提取記者資訊
                    for text in text_fields:
                        author = self._extract_reporter_names_from_html(text)
                        if author:
                            return author
                            
                except json.JSONDecodeError:
                    continue
                    
            return None
            
        except Exception as e:
            self.logger.error(f"從JSON-LD提取記者資訊失敗: {e}")
            return None

    def _extract_reporter_from_meta(self, html_content: str) -> Optional[str]:
        """從meta標籤中提取記者資訊"""
        try:
            import re
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 檢查各種meta標籤
            meta_tags = soup.find_all('meta')
            
            for tag in meta_tags:
                # 檢查content屬性
                content = tag.get('content', '')
                if content and '記者' in content:
                    author = self._extract_reporter_names_from_html(content)
                    if author:
                        return author
                
                # 檢查name或property屬性
                name = tag.get('name', '') or tag.get('property', '')
                if name and ('author' in name.lower() or 'creator' in name.lower()):
                    content = tag.get('content', '')
                    if content:
                        # 如果直接是作者名稱
                        clean_name = content.strip()
                        if re.match(r'^[\u4e00-\u9fff]{2,4}$', clean_name):
                            return clean_name
            
            return None
            
        except Exception as e:
            self.logger.error(f"從meta標籤提取記者資訊失敗: {e}")
            return None


def test_ltn_scraper():
    """測試LTN爬蟲"""
    print("測試LTN爬蟲 (ORM版本)")
    print("="*30)
    
    scraper = LTNScraper()
    result = scraper.scrape_news(max_pages=1)  # 限制1頁做測試
    
    print("\n執行結果:")
    print(f"總計: {result['total']}")
    print(f"新增: {result['new']}")
    print(f"跳過: {result['skipped']}")
    print(f"失敗: {result['failed']}")


if __name__ == "__main__":
    test_ltn_scraper()

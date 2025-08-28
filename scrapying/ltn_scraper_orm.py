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
from base_scraper_orm import BaseNewsScraper


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
            # 直接從新聞頁面提取記者資訊
            author = self._extract_reporter_names(news_url)
            
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
            # 使用多種正則表達式模式提取記者資訊
            patterns = [
                r"〔記者(.*?)／",        # 〔記者XXX／
                r"記者(.*?)／",          # 記者XXX／
                r"記者(.*?)攝",          # 記者XXX攝
                r"(.*?)攝\）",           # XXX攝）
                r"(.*?)攝",              # XXX攝
                r"採訪(.*?)／",          # 採訪XXX／
                r"撰稿(.*?)／",          # 撰稿XXX／
            ]
            
            all_matches = []
            for pattern in patterns:
                matches = re.findall(pattern, html_content)
                if matches:
                    all_matches.extend(matches)
            
            if all_matches:
                # 分割名字並去重和清理
                names = set()
                for match in all_matches:
                    # 處理多個記者名稱（用「、」分隔）
                    for name in match.split("、"):
                        clean_name = name.strip()
                        # 去除常見的後綴（攝影、攝）、括弧等）
                        clean_name = re.sub(r'[攝影、攝）\)]+.*$', '', clean_name)
                        # 只保留中文姓名（2-4個字符）
                        if re.match(r'^[\u4e00-\u9fff]{2,4}$', clean_name):
                            names.add(clean_name)
                
                if names:
                    return ', '.join(sorted(names))  # 排序保持一致性
            
            return None
            
        except Exception as e:
            self.logger.error(f"從HTML提取記者名稱失敗: {e}")
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

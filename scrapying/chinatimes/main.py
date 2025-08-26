import requests
from bs4 import BeautifulSoup
from datetime import datetime
import random
import time
from fake_useragent import UserAgent
import re
import hashlib
import sys
import os

# 添加父目錄到Python路徑，以便導入database模組
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database import news_db


def get_author_from_news_page(news_url, headers):
    """從新聞詳細頁面提取作者信息"""
    try:
        time.sleep(random.uniform(0.5, 1.5))  # 短暫延遲避免過於頻繁請求
        response = requests.get(news_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 尋找作者信息 - 根據你提供的HTML結構
        author_div = soup.find("div", class_="author")
        if author_div:
            author_link = author_div.find("a")
            if author_link:
                return author_link.get_text(strip=True)
        
        # 備用方案：尋找其他可能的作者格式
        # 方案1: 查找記者XXX模式
        text_content = soup.get_text()
        author_patterns = [
            r'記者([^\s\n]{1,10})[／/]',  # 記者XXX/
            r'記者([^\s\n]{1,10})報導',   # 記者XXX報導
            r'文[／/]([^\s\n]{1,10})',    # 文/XXX
            r'([^\s\n]{1,10})[／/]綜合報導', # XXX/綜合報導
        ]
        
        for pattern in author_patterns:
            match = re.search(pattern, text_content)
            if match:
                author_name = match.group(1).strip()
                if author_name and len(author_name) <= 10 and len(author_name) >= 1:
                    return author_name
        
        return "中國時報"  # 找不到就用預設值
        
    except Exception as e:
        print(f"提取作者信息時發生錯誤: {e}")
        return "中國時報"


def insert_news_to_db(news_items):
    """
    將新聞數據插入到資料庫中
    
    Args:
        news_items: 新聞數據列表
        
    Returns:
        int: 成功插入的數量
    """
    return news_db.insert_news_batch(news_items)


def create_news_table():
    """創建新聞表格（如果不存在）- 使用統一數據庫模組"""
    # 表已經在database模組中自動創建
    pass


def is_today_news_by_url(news_url, today_date_str):
    """從URL中提取日期來檢查是否為今天的新聞"""
    # 從URL提取日期部分，格式如: /realtimenews/20250826002838-260407
    # 前8位是日期: 20250826 (YYYYMMDD)
    url_match = re.search(r'/realtimenews/(\d{8})\d{6}-\d{6}', news_url)
    if url_match:
        url_date = url_match.group(1)  # 例如: "20250826"
        return url_date == today_date_str
    
    return True  # 如果無法從URL解析日期，假設是今天的


def scrape_page(url, page_num, headers, today_date_str, max_news_per_page=20):
    """抓取單一頁面的新聞"""
    page_url = f"{url}&page={page_num}" if page_num > 1 else url
    print(f"正在抓取第 {page_num} 頁: {page_url}")
    
    try:
        # 發送 HTTP 請求，加入延遲
        time.sleep(random.uniform(1, 3))  # 隨機延遲 1-3 秒
        response = requests.get(page_url, headers=headers)
        response.raise_for_status()  # 檢查請求是否成功

        # 解析 HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # 提取每則新聞
        page_news_items = []
        processed_count = 0
        found_non_today_news = False
        
        # 找到所有的新聞連結 (通過 a 標籤直接找到新聞連結)
        news_links = soup.find_all("a", href=True)
        
        for a_tag in news_links:
            if processed_count >= max_news_per_page:
                break
                
            href = a_tag.get("href", "")
            if isinstance(href, str) and "/realtimenews/" in href:
                # 提取標題
                title = a_tag.get_text(strip=True)
                
                # 過濾掉空標題或太短的標題
                if not title or len(title) < 5:
                    continue
                    
                # 確保網址為絕對路徑
                link = href
                if not link.startswith("http"):
                    link = f"https://www.chinatimes.com{link}"
                
                # 首先檢查URL中的日期是否為今天
                if not is_today_news_by_url(link, today_date_str):
                    print(f"發現非今天的新聞 (從URL判斷): {link}")
                    found_non_today_news = True
                    break
                
                # 嘗試找到時間、作者和分類信息
                time_info = ""
                author = "中國時報"  # 預設作者
                category = "政治"
                
                try:
                    # 尋找父元素或鄰近元素中的時間信息
                    parent_text = ""
                    if a_tag.parent:
                        parent_text = a_tag.parent.get_text()
                        
                    # 尋找時間格式 (如: 14:35 2025/08/26)
                    time_match = re.search(r'\d{2}:\d{2}\s*\d{4}/\d{2}/\d{2}', parent_text)
                    if time_match:
                        time_info = time_match.group()
                    
                    # 從新聞詳細頁面提取作者信息
                    print(f"正在提取作者信息 ({processed_count+1}/{max_news_per_page}): {title[:30]}...")
                    author = get_author_from_news_page(link, headers)
                    
                    # 尋找分類標籤
                    if "新聞" in parent_text:
                        category = "新聞"
                    elif "政治" in parent_text:
                        category = "政治"
                except Exception as e:
                    print(f"處理新聞時發生錯誤: {e}")
                    pass

                # 生成唯一ID (使用URL後面的部分，如: 20250826002838-260407)
                news_id = ""
                # 從URL提取新聞ID，格式如: /realtimenews/20250826002838-260407
                url_match = re.search(r'/realtimenews/(\d{14}-\d{6})', link)
                if url_match:
                    news_id = url_match.group(1)
                else:
                    # 如果無法從URL提取，則使用MD5作為備用方案
                    news_id = hashlib.md5(link.encode('utf-8')).hexdigest()
                
                # 檢查是否已經在當前批次中處理過這個新聞
                already_processed = any(item["id"] == news_id for item in page_news_items)
                
                # 避免重複添加相同的新聞
                if not already_processed:
                    page_news_items.append(
                        {
                            "id": news_id,
                            "news_name": "中國時報",
                            "author": author,  # 使用提取的作者信息
                            "title": title,
                            "url": link,
                            "publish_time": time_info or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                    )
                    processed_count += 1

        return page_news_items, found_non_today_news
        
    except Exception as e:
        print(f"抓取第 {page_num} 頁時發生錯誤: {e}")
        return [], False


# 隨機 User-Agent
ua = UserAgent()
headers = {"User-Agent": ua.random}

# 目標 URL (基礎URL，會加上page參數)
base_url = "https://www.chinatimes.com/politic/total/?chdtv"

# 連接到數據庫
# 使用統一的數據庫模組，不再需要手動連接


# 確保表格存在
create_news_table()

# 獲取今天的日期
today = datetime.now()
today_date_str = today.strftime("%Y%m%d")  # 格式: 20250826
print(f"今天的日期: {today_date_str}")

# 主要爬取邏輯
try:
    all_news_items = []
    current_page = 1
    max_pages = 10  # 最大頁數限制
    
    print("開始抓取中國時報政治新聞，將抓取到非今天的新聞為止...")
    
    while current_page <= max_pages:
        try:
            page_news_items, found_non_today_news = scrape_page(
                base_url, current_page, headers, today_date_str
            )
            
            if page_news_items:
                all_news_items.extend(page_news_items)
                print(f"第 {current_page} 頁抓取到 {len(page_news_items)} 則新聞")
            else:
                print(f"第 {current_page} 頁沒有抓取到新聞")
            
            # 如果發現非今天的新聞，停止爬取
            if found_non_today_news:
                print(f"在第 {current_page} 頁發現非今天的新聞，停止爬取")
                break
                
            current_page += 1
            
        except Exception as e:
            print(f"抓取第 {current_page} 頁時發生錯誤: {e}")
            current_page += 1
            continue

    # 將數據插入到數據庫中
    if all_news_items:
        insert_count = insert_news_to_db(all_news_items)
        
        print(f"\n數據已成功保存到 news.db，共抓取了 {len(all_news_items)} 則新聞")
        print(f"其中 {insert_count} 則新聞是新增的")
        
        # 顯示前5則新聞作為示例
        print("\n前5則新聞預覽:")
        for i, item in enumerate(all_news_items[:5]):
            print(f"{i+1}. {item['title']}")
            print(f"   作者: {item['author']}")
            print(f"   發布時間: {item['publish_time']}")
            print(f"   網址: {item['url']}\n")
    else:
        print("沒有抓取到任何新聞")

except Exception as e:
    print(f"發生錯誤：{e}")
finally:
    print("爬取完成")

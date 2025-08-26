from datetime import datetime, timedelta
import json
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import pytz
import traceback
import sys
from time import sleep
import re
import os

# 添加父目錄到Python路徑，以便導入database模組
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database import news_db

# Define the base URL and the target URL
BASE_URL = "https://news.ltn.com.tw"
TARGET_URL = "https://news.ltn.com.tw/ajax/breakingnews/politics"
NEWS_NAME = "ltn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7,sl;q=0.6",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1"
}

taipei_tz = pytz.timezone('Asia/Taipei')


def is_today_news(publish_time_str, today_date_str):
    """Check if the given publish time is from today."""
    try:
        # Handle different time formats
        if ' ' not in publish_time_str:
            # Only time, add today's date
            today_date_full = datetime.now(taipei_tz).strftime("%Y/%m/%d")
            publish_time_str = f"{today_date_full} {publish_time_str}"
        
        # Parse the publish time string in format "2025/08/26 15:30"
        news_date = datetime.strptime(publish_time_str, "%Y/%m/%d %H:%M")
        news_date_str = news_date.strftime("%Y%m%d")
        return news_date_str == today_date_str
    except (ValueError, AttributeError):
        return False


def news_contains(news_id):
    return f"https://news.ltn.com.tw/articleAjax/breakingnews/{news_id}/2"


async def fetch(url, session, params=None):
    """Fetch a URL using aiohttp."""
    try:
        if params is None:
            async with session.get(url, headers=HEADERS) as response:
                if response.status == 403:  # handle forbidden response
                    print(f"403 Forbidden encountered for URL: {url}")
                    return None
                return await response.text()
        else:
            async with session.get(url, params=params, headers=HEADERS) as response:
                if response.status == 403:  # handle forbidden response
                    print(f"403 Forbidden encountered for URL: {url}")
                    return None
                return await response.text()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


async def fetch_all(urls, proxies=None):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(url, session)
                 for i, url in enumerate(urls)]
        return await asyncio.gather(*tasks)


def extract_reporter_names_from_html(html_content):
    pattern = r"〔記者(.*?)／"
    matches = re.findall(pattern, html_content)

    if matches:
        # 分割名字並去重
        names = set()
        for match in matches:
            for name in match.split("、"):
                names.add(name.strip())
        return ', '.join(names)
    return None


async def extract_reporter_names(news_id, session):
    async with session.get(news_contains(news_id), headers=HEADERS) as response:
        text = await response.text()
        result = json.loads(text)
        try:
            return extract_reporter_names_from_html(result['A_Html'])
        except:
            return None


def news_exists(news_id):
    """Check if a news with the given ID already exists in the database."""
    return news_db.news_exists(news_id)


def insert_news_with_author(news_info, author):
    news_id = news_info["news_id"]
    news_name = news_info["news_name"]
    title = news_info["title"]
    url = news_info["url"]
    publish_time = news_info["publish_time"]
    
    news_item = {
        "id": news_id,
        "news_name": news_name,
        "author": author,
        "title": title,
        "url": url,
        "publish_time": publish_time
    }
    return news_db.insert_news_item(news_item)


async def fetch_news_content(news_url, session):
    try:
        async with session.get(news_url, headers=HEADERS) as response:
            if response.status == 403:  # handle forbidden response
                print(f"403 Forbidden encountered for URL: {news_url}")
                return None, None
            text = await response.text()
            return news_url, text
    except Exception as e:
        print(f"Error fetching {news_url}: {e}")
        return None, None


async def fetch_news_info(url, session):
    async with session.get(url, headers=HEADERS) as response:
        if response.status == 200:
            return await response.json()
        else:
            return None


# 處理單條新聞資訊，儲存除了 author 以外的部分
async def process_news_item(news_item):
    news_id = news_item['no']
    title = news_item['title']
    url = news_item['url']
    time_str = news_item['time']

    # 检查时间字符串是否只有时间没有日期
    if ' ' not in time_str:
        # 只有时间，没有日期
        today_date_str = datetime.now().strftime("%Y/%m/%d")
        publish_time = f"{today_date_str} {time_str}"
    else:
        # 已包含日期和时间
        publish_time = time_str

    return {
        "news_id": news_id,
        "news_name": NEWS_NAME,
        "title": title,
        "url": url,
        "publish_time": publish_time,
    }


async def main():
    # 獲取今天的日期（格式：20250826）
    today = datetime.now(taipei_tz)
    today_date_str = today.strftime("%Y%m%d")
    print(f"今天的日期: {today_date_str}")
    print("開始抓取LTN政治新聞，只抓取今天的新聞...")

    page = 1
    news_info_list = []
    found_non_today_news = False

    async with aiohttp.ClientSession() as session:
        while not found_non_today_news:
            print(f"目前在撈：第{page}頁")
            current_url = f"{TARGET_URL}/{page}"
            page_data = await fetch_news_info(current_url, session)

            if not page_data or "data" not in page_data:
                break

            news_data = page_data["data"]

            if isinstance(news_data, dict):
                news_data = news_data.values()
            
            page_today_count = 0
            for news_item in news_data:
                news_info = await process_news_item(news_item)
                
                # Check if this news is from today
                if is_today_news(news_info["publish_time"], today_date_str):
                    news_info_list.append(news_info)
                    page_today_count += 1
                else:
                    print(f"發現非今天的新聞，停止抓取: {news_info['publish_time']}")
                    found_non_today_news = True
                    break
            
            print(f"本頁找到 {page_today_count} 則今天的新聞")
            
            if found_non_today_news:
                break

            page += 1
            await asyncio.sleep(1)  # 避免过快请求

        # 處理今天的新聞
        for news_info in news_info_list:
            if not news_exists(news_info["news_id"]):
                print(f"處理今天的新聞: {news_info['title'][:50]}...")
                author = await extract_reporter_names(news_info["news_id"], session)
                insert_news_with_author(news_info, author)
        
        print(f"LTN新聞處理完成，共處理 {len(news_info_list)} 則今天的新聞")

try:
    # Run the asyncio event loop
    asyncio.run(main())

except Exception as e:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback_details = traceback.extract_tb(exc_traceback)
    filename, line, func, text = traceback_details[-1]

    print(f"Exception occurred in file {filename} on line {line}: {e}")
finally:
    print("LTN爬取完成")

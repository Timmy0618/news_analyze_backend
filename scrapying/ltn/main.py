from datetime import datetime, timedelta
import json
import asyncio
import aiohttp
import sqlite3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import pytz
import traceback
import sys
from time import sleep
import re
# Connect to SQLite database
conn = sqlite3.connect("./scrapying/news.db")
cursor = conn.cursor()

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


async def fetch_all(urls):
    """Fetch all URLs in the given list concurrently."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(url, session) for url in urls]
        return await asyncio.gather(*tasks)


def extract_author_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    # 尋找特定的 <div> 標籤
    target_div = soup.find('div', class_='text boxTitle boxText')
    if not target_div:
        return ""

    # 從該 <div> 標籤中取得所有的 <p> 標籤內容
    paragraphs = [p.get_text() for p in target_div.find_all('p')]

    # 使用正則表達式匹配常見的記者名稱模式
    reporter_patterns = [
        r"〔記者(\w+)",
        r"文／(\w+)",
        r"撰文：(\w+)"
    ]

    reporter_names_set = set()

    for paragraph in paragraphs:
        for pattern in reporter_patterns:
            matches = re.findall(pattern, paragraph)
            for match in matches:
                if not match.endswith("攝"):
                    reporter_names_set.add(match)

    # 將 set 轉換為逗號分隔的字串進行回傳
    return ', '.join(reporter_names_set)


def news_exists(news_id):
    """Check if a news with the given ID already exists in the database."""
    cursor.execute(
        "SELECT id FROM news WHERE id=? and news_name=?", (news_id, NEWS_NAME,))
    return cursor.fetchone() is not None


def insert_news(news_id, news_name, author, title, url, publish_time):
    """Insert news details into the database."""
    cursor.execute("INSERT INTO news (id, news_name, author, title, url, publish_time) VALUES (?, ?, ?, ?, ?, ?)",
                   (news_id, news_name, author, title, url, publish_time))


async def fetch_news_content(news):
    html_content = await fetch_all([news['url']])
    if not html_content or html_content[0] is None:
        return (None, None)

    author = extract_author_from_html(html_content[0])
    return (news, author)


async def main():
    taipei_tz = pytz.timezone('Asia/Taipei')
    seven_days_ago = datetime.now(taipei_tz) - timedelta(days=7)
    page = 1
    news_hrefs = []
    should_continue = True

    while should_continue:
        sleep(1)
        print(f"正在撈取第：{page}頁")

        if page > 25:
            break

        current_url = f"{TARGET_URL}/{page}"
        target_page_htmls = await fetch_all([current_url])
        if not target_page_htmls or target_page_htmls[0] is None:
            print(f"Failed to fetch data for page {page}. Skipping...")
            page += 1
            continue

        result = json.loads(target_page_htmls[0])

        # Determine if the result is a list or a dictionary
        if isinstance(result['data'], list):
            news_list = result['data']
        else:  # Dictionary format for subsequent pages
            news_list = result['data'].values()

        # Extract URLs from the relevant articles
        for news in news_list:
            news_time_str = news['time']
            if ' ' in news_time_str:  # Contains both date and time
                news_date = datetime.strptime(news_time_str, "%Y/%m/%d %H:%M")
            else:  # Only time is present
                today_date_str = datetime.now(taipei_tz).strftime("%Y/%m/%d")
                combined_str = today_date_str + " " + news_time_str
                news_date = datetime.strptime(combined_str, "%Y/%m/%d %H:%M")

            news_date = taipei_tz.localize(news_date)
            news['time'] = news_date.strftime("%Y-%m-%d %H:%M:%S")

            if news_date < seven_days_ago:
                should_continue = False
                break

            if news_exists(news['no']):
                print(f"{news['no']}exist")
                break

            news_hrefs.append(news)
        # Increment the page number for the next iteration
        page += 1

    # Step 1: Fetch all news content asynchronously
    tasks = [fetch_news_content(news) for news in news_hrefs]
    results = await asyncio.gather(*tasks)

    # Step 2: Handle database operations in the main thread
    for news, author in results:
        if news['no'] is None:
            continue

        if news_exists(news['no']):
            break

        insert_news(str(news['no']), NEWS_NAME, str(author),
                    str(news['title']), str(news['url']), str(news['time']))

    conn.commit()

try:
    # Run the asyncio event loop
    asyncio.run(main())

except Exception as e:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback_details = traceback.extract_tb(exc_traceback)
    filename, line, func, text = traceback_details[-1]

    print(f"Exception occurred in file {filename} on line {line}: {e}")
finally:
    # Close database connection
    conn.close()

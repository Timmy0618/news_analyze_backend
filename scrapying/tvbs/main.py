from datetime import datetime, timedelta
import json
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import pytz
import traceback
import sys
import os

# 添加父目錄到Python路徑，以便導入database模組
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database import news_db

# Define the base URL and the target URL
BASE_URL = "https://news.tvbs.com.tw"
TARGET_URL = "https://news.tvbs.com.tw/politics"
NEWS_NAME = "tvbs"


async def fetch(url, session, params=None):
    """Fetch a URL using aiohttp."""
    if params is None:
        async with session.get(url) as response:
            return await response.text()
    else:
        async with session.get(url, params=params) as response:
            return await response.text()


async def fetch_all(urls):
    """Fetch all URLs in the given list concurrently."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(url, session) for url in urls]
        return await asyncio.gather(*tasks)


def get_newest_href(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    # 提取包含 "/politics/" 的所有 href 值
    href_values = [a['href'] for a in soup.find_all(
        'a', href=True) if "/politics/" in a['href']]

    return href_values


def extract_payload(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all input elements inside the container with class "politics"
    inputs = soup.select('div.container.politics input')

    # Extract the 'id' and 'value' attributes for each input element
    payload = {input_element['id']: input_element['value']
               for input_element in inputs if input_element.has_attr('value')}

    return payload


def transform_payload(payload):
    """Transform the payload into the desired format."""
    transformed = {
        'news_id': payload['last_news_id'],
        'page': payload['breaking_news_page'],
        'date': payload['last_news_review_date'],
        'cate': payload['breaking_news_cate'],
        'get_num': payload['breaking_news_get_num']
    }
    return transformed


def create_payload_from_new_page(new_page_data):
    """Creates a new payload using data from the new page."""
    payload = {
        'news_id': new_page_data['last_news_id'],
        'date': new_page_data['last_news_review_date'],
        # Default to '2' if not found
        'page': new_page_data.get('page'),
        # Default to '7' if not found
        'cate': new_page_data.get('cate'),
        # Default to '90' if not found
        'get_num': new_page_data.get('get_num')
    }
    return payload


async def get_new_page_html(payload):

    # Construct the GET request URL using the payload
    get_url = "https://news.tvbs.com.tw/news/get_breaking_news_other_cate?"

    async with aiohttp.ClientSession() as session:
        response_text = await fetch(get_url, session, payload)

    # Fetch the GET request
    return json.loads(response_text)


def get_news_links_from_html(html_content):
    """Extracts news links and publish times from the HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")
    # 首先，我們將尋找具有 class="article_pack" 的 <article> 元素
    article_element = soup.find("article", class_="article_pack")

    # 然後，尋找具有 class="list" 的 <div> 元素
    div_list = article_element.find(
        "div", class_="list") if article_element else None

    # 從該 <div> 中找到所有 <li> 元素
    li_elements = div_list.find_all("li") if div_list else []

    hrefs = []

    for li in li_elements:
        # 對於每個 <li>，尋找 <a> 標籤並提取 href 屬性
        a_tag = li.find("a")
        if a_tag and "href" in a_tag.attrs:
            hrefs.append(urljoin(BASE_URL, a_tag["href"]))

    return hrefs


def extract_details_from_html(html_content):
    # Parse the content using BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    # Check for 404 error
    if soup.find('div', class_='error_div'):
        return "404 Error", None, None

    # Extract title
    title = soup.find('h1', class_='title').text.strip()

    # Extract author and date
    author_div = soup.find('div', class_='author')
    if author_div and author_div.a:
        author = author_div.a.text.strip()
    else:
        author = ""

    date_str = ""
    for line in author_div.stripped_strings:
        if "發佈時間：" in line:
            date_str = line.replace("發佈時間：", "").strip()

    return title, author, date_str


def is_today_news(date_str, today_date_str):
    """Check if the given date string is from today."""
    try:
        # Parse the date string in format "2025/08/26 15:30"
        news_date = datetime.strptime(date_str, "%Y/%m/%d %H:%M")
        news_date_str = news_date.strftime("%Y%m%d")
        return news_date_str == today_date_str
    except (ValueError, AttributeError):
        return False


async def main():
    taipei_tz = pytz.timezone('Asia/Taipei')
    
    # 獲取今天的日期（格式：20250826）
    today = datetime.now(taipei_tz)
    today_date_str = today.strftime("%Y%m%d")
    print(f"今天的日期: {today_date_str}")
    print("開始抓取TVBS政治新聞，只抓取今天的新聞...")

    current_url = f"{TARGET_URL}"
    target_page_htmls = await fetch_all([current_url])

    payload = extract_payload(target_page_htmls[0])
    date_str = payload['last_news_review_date']
    payload = transform_payload(payload)

    all_hrefs = set()
    found_non_today_news = False

    # Get initial hrefs
    hrefs = get_newest_href(target_page_htmls[0])
    all_hrefs.update(hrefs)

    # Continue fetching pages until we find non-today news
    while not found_non_today_news:
        try:
            new_page = await get_new_page_html(payload)
            hrefs = get_newest_href(new_page['breaking_news_other'])
            
            # Check each news item to see if it's from today
            page_today_count = 0
            for href in hrefs:
                # Extract news details to check date
                news_url = f"{BASE_URL}{href}"
                news_html = await fetch_all([news_url])
                
                if news_html[0] is not None:
                    title, author, news_date_str = extract_details_from_html(news_html[0])
                    if news_date_str and is_today_news(news_date_str, today_date_str):
                        all_hrefs.add(href)
                        page_today_count += 1
                    elif news_date_str and not is_today_news(news_date_str, today_date_str):
                        print(f"發現非今天的新聞，停止抓取: {news_date_str}")
                        found_non_today_news = True
                        break
            
            print(f"本頁找到 {page_today_count} 則今天的新聞")
            
            if found_non_today_news:
                break

            # Extract new payload and remove 'breaking_news_other' key
            payload = create_payload_from_new_page(new_page)
            date_str = new_page['last_news_review_date']
            
        except Exception as e:
            print(f"抓取頁面時發生錯誤: {e}")
            break

    print(f"共找到 {len(all_hrefs)} 則今天的新聞連結")

    async def extract_and_insert_news(news_href):
        news_url = f"{BASE_URL}{news_href}"
        news_html = await fetch_all([news_url])

        if news_html[0] is None:
            print("html none")
            return

        # Extract news ID from href
        news_id = news_href.split('/')[-1]

        # Check if the news ID already exists in the database using unified database
        if news_db.news_exists(news_url):
            print(f"News with ID {news_id} already exists in the database. Skipping...")
            return

        title, author, date_str = extract_details_from_html(news_html[0])
        if title == "404 Error":
            print(f"Error 404: Skipping article at {news_url}")
            return

        if date_str:
            # Since we've already filtered for today's news in main(), we can directly insert
            print(f"插入今天的新聞: {title[:50]}...")
            news_item = {
                "title": title,
                "link": news_url,
                "content": f"作者: {author}",
                "date": date_str,
                "source": "TVBS"
            }
            news_db.insert_news_item(news_item)

    print(f"開始處理 {len(all_hrefs)} 則新聞...")
    coroutines = [extract_and_insert_news(
        news_href) for news_href in all_hrefs]
    await asyncio.gather(*coroutines)
    
    print(f"TVBS新聞處理完成")


try:
    # Run the asyncio event loop
    asyncio.run(main())

except Exception as e:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback_details = traceback.extract_tb(exc_traceback)
    filename, line, func, text = traceback_details[-1]

    print(f"ERROR: {e}")
    print(f"File: {filename}, Line: {line}, Function: {func}")
    print(f"Code: {text}")

finally:
    print("TVBS爬取完成")

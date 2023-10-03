from datetime import datetime, timedelta
import re
import asyncio
import aiohttp
import sqlite3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import pytz
# Connect to SQLite database
conn = sqlite3.connect("./scrapying/news.db")
cursor = conn.cursor()

# Define the base URL and the target URL
BASE_URL = "https://news.tvbs.com.tw/"
TARGET_URL = "https://news.tvbs.com.tw/politics"
NEWS_NAME = "tvbs"


async def fetch(url, session):
    """Fetch a URL using aiohttp."""
    async with session.get(url) as response:
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
    print(href_values)
    # 從 href 值中提取 ID 並找出最大的 ID
    max_id = max([int(href.split('/')[-1]) for href in href_values])

    return max_id


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


def is_within_seven_days(date_str, taipei_tz):
    """Check if the given date string is within the last seven days."""
    news_date = datetime.strptime(date_str, "%Y/%m/%d %H:%M")
    news_date = taipei_tz.localize(news_date)
    seven_days_ago = datetime.now(taipei_tz) - timedelta(days=7)
    return news_date > seven_days_ago


def news_exists(news_id):
    """Check if a news with the given ID already exists in the database."""
    cursor.execute("SELECT id FROM news WHERE id=?", (news_id,))
    return cursor.fetchone() is not None


def insert_news(news_id, news_name, author, title, url, publish_time):
    """Insert news details into the database."""
    cursor.execute("INSERT INTO news (id, news_name, author, title, url, publish_time) VALUES (?, ?, ?, ?, ?, ?)",
                   (news_id, news_name, author, title, url, publish_time))
    conn.commit()


async def main():
    taipei_tz = pytz.timezone('Asia/Taipei')
    seven_days_ago = datetime.now(taipei_tz) - timedelta(days=7)

    # Prepare the SQL statement for checking the existence of news ID
    check_sql = "SELECT COUNT(*) FROM news WHERE id = ?"

    # Prepare the SQL statement for inserting the news into the database
    insert_sql = "INSERT INTO news (id, news_name, author, title, url, publish_time) VALUES (?, ?, ?, ?, ?, ?)"

    current_url = f"{TARGET_URL}"
    target_page_htmls = await fetch_all([current_url])
    max_news_id = get_newest_href(target_page_htmls[0])
    count = 0
    publish_time = ""
    while True:

        for news_id in range(max_news_id, max_news_id - 10, -1):
            print(f"目前在撈：ID {news_url}")

            news_url = f"{BASE_URL}politics/{news_id}"
            news_html = await fetch_all([news_url])

            # Check if the news ID already exists in the database
            cursor.execute(check_sql, (news_id,))
            exists = cursor.fetchone()[0]

            if not exists:
                title, author, date_str = extract_details_from_html(
                    news_html[0])
                if title == "404 Error":
                    print(
                        f"Error 404: Skipping article at {BASE_URL + str(max_news_id)}")
                    continue

                publish_time = datetime.strptime(
                    date_str, "%Y/%m/%d %H:%M").replace(tzinfo=taipei_tz)
                if publish_time < seven_days_ago:
                    break
                cursor.execute(insert_sql, (news_id, NEWS_NAME,
                               author, title, news_url, date_str))
                conn.commit()
            else:
                print(
                    f"News with ID {news_id} already exists in the database. Skipping...")

        count += 1
        max_news_id -= 10
        # Check the date of the oldest news article
        if publish_time and publish_time < seven_days_ago:
            break
        else:
            if count > 50:
                break


# Run the asyncio event loop
asyncio.run(main())

# Close database connection
conn.close()

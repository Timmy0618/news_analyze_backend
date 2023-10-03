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
BASE_URL = "https://www.setn.com/"
TARGET_URL = "https://www.setn.com/ViewAll.aspx?PageGroupID=6"
NEWS_NAME = "setn"


def extract_author(text):
    patterns = [
        re.compile(r'記者(\S+)／\S+報導'),  # Match "記者陳怡潔／台北報導"
        re.compile(r'政治中心／(\S+)報導'),  # Match "政治中心／張家寧報導"
        re.compile(r'文、圖／(\S+)'),  # Match "文、圖／鏡週刊"
        re.compile(r'圖、文／(\S+)'),  # Match "文、圖／鏡週刊"
        re.compile(r'文／(\S+)'),  # Match "文、圖／鏡週刊"
        re.compile(r'文／\S+／(\S+)'),  # Match "文／住展雜誌／陳曼羚"
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None  # Return None if no pattern matches


async def fetch(url, session):
    """Fetch a URL using aiohttp."""
    async with session.get(url) as response:
        return await response.text()


async def fetch_all(urls):
    """Fetch all URLs in the given list concurrently."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(url, session) for url in urls]
        return await asyncio.gather(*tasks)


def get_news_links_from_html(html_content):
    """Extracts news links and publish times from the HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")

    current_year = datetime.now().year  # Get the current year
    taipei_tz = pytz.timezone('Asia/Taipei')  # Set the Taipei timezone

    extracted_data = []
    for item in soup.find_all('div', class_='col-sm-12 newsItems'):
        link_tag = item.find('a', href=True, class_='gt')
        time_tag = item.find('time')
        if link_tag and time_tag:
            link = urljoin(BASE_URL, link_tag['href'])
            parsed_url = urlparse(link)
            news_id = parse_qs(parsed_url.query).get('NewsID')
            if news_id:
                cleaned_link = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?NewsID={news_id[0]}"

                # Add the current year to the parsed time and adjust the timezone
                publish_time = datetime.strptime(
                    f"{current_year}/{time_tag.text}", '%Y/%m/%d %H:%M')
                publish_time = taipei_tz.localize(
                    publish_time)  # Set the timezone to Taipei
                # Convert to string in your desired format
                publish_time_str = publish_time.strftime('%Y-%m-%d %H:%M:%S')

                extracted_data.append((cleaned_link, publish_time_str))

    return extracted_data


def extract_details_from_html(html_content):
    """Extracts the news title, author, and publish time from the given HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract title
    title_div = soup.find("div", class_="photo-full-title pull-left")
    news_title = title_div.get_text(strip=True).split(" | ")[
        0] if title_div else None

    # Extract author
    author_div = soup.find("div", id="ckuse", itemprop="articleBody")
    news_author = None
    if author_div:
        author_tag = author_div.find("p")
        if author_tag:
            author_text = author_tag.get_text(strip=True)
            news_author = extract_author(author_text)

    return news_title, news_author


async def main():
    taipei_tz = pytz.timezone('Asia/Taipei')
    seven_days_ago = datetime.now(taipei_tz) - timedelta(days=7)

    page = 1
    while True:
        print(f"目前在撈：第{page}頁")
        current_url = f"{TARGET_URL}&p={page}"
        target_page_htmls = await fetch_all([current_url])
        news_data = get_news_links_from_html(target_page_htmls[0])

        # Check if the earliest news on the page is within the last 7 days
        earliest_news_time = min(data[1] for data in news_data)
        earliest_news_datetime = datetime.strptime(
            earliest_news_time, '%Y-%m-%d %H:%M:%S')
        earliest_news_datetime = taipei_tz.localize(earliest_news_datetime)

        if earliest_news_datetime < seven_days_ago:
            break  # Stop if the news is older than 7 days

        # Fetch each news link concurrently
        news_links = [data[0] for data in news_data]
        news_htmls = await fetch_all(news_links)

        # Process each news HTML content
        for (link, publish_time), html_content in zip(news_data, news_htmls):
            news_id = link.split('NewsID=')[-1]
            cursor.execute('SELECT id FROM news WHERE id = ?', (news_id,))
            if cursor.fetchone() is None:
                title, author = extract_details_from_html(html_content)
                cursor.execute('INSERT INTO news (id, news_name, author, title, url, publish_time) VALUES (?, ?, ?, ?, ?, ?)',
                               (news_id, NEWS_NAME, author, title, link, publish_time))
                conn.commit()

        page += 1  # Go to the next page


# Run the asyncio event loop
asyncio.run(main())

# Close database connection
conn.close()

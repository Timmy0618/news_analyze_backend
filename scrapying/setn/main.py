from datetime import datetime, timedelta
import re
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import pytz
import sys
import os

# 添加父目錄到Python路徑，以便導入database模組
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database import news_db

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


def is_today_news(publish_time_str, today_date_str):
    """Check if the given publish time is from today."""
    try:
        # Parse the publish time string in format "2025-08-26 15:30:00"
        news_date = datetime.strptime(publish_time_str, "%Y-%m-%d %H:%M:%S")
        news_date_str = news_date.strftime("%Y%m%d")
        return news_date_str == today_date_str
    except (ValueError, AttributeError):
        return False


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
    
    # 獲取今天的日期（格式：20250826）
    today = datetime.now(taipei_tz)
    today_date_str = today.strftime("%Y%m%d")
    print(f"今天的日期: {today_date_str}")
    print("開始抓取SETN政治新聞，只抓取今天的新聞...")

    page = 1
    found_non_today_news = False
    
    while not found_non_today_news:
        print(f"目前在撈：第{page}頁")
        current_url = f"{TARGET_URL}&p={page}"
        target_page_htmls = await fetch_all([current_url])
        news_data = get_news_links_from_html(target_page_htmls[0])

        # Check each news item to see if it's from today
        page_today_count = 0
        for data in news_data:
            link, publish_time = data
            
            # Check if this news is from today
            if is_today_news(publish_time, today_date_str):
                page_today_count += 1
            else:
                print(f"發現非今天的新聞，停止抓取: {publish_time}")
                found_non_today_news = True
                break
        
        print(f"本頁找到 {page_today_count} 則今天的新聞")
        
        if found_non_today_news:
            break

        # Fetch each news link concurrently (only for today's news)
        today_news_data = [(link, publish_time) for link, publish_time in news_data 
                          if is_today_news(publish_time, today_date_str)]
        
        if today_news_data:
            news_links = [data[0] for data in today_news_data]
            news_htmls = await fetch_all(news_links)

            # Process each news HTML content
            for (link, publish_time), html_content in zip(today_news_data, news_htmls):
                news_id = link.split('NewsID=')[-1]
                
                # Check if news exists using unified database
                if not news_db.news_exists(news_id):
                    title, author = extract_details_from_html(html_content)
                    
                    print(f"插入今天的新聞: {title[:50] if title else 'No title'}...")
                    
                    # Insert using unified database
                    news_item = {
                        "id": news_id,
                        "news_name": NEWS_NAME,
                        "author": author,
                        "title": title,
                        "url": link,
                        "publish_time": publish_time
                    }
                    news_db.insert_news_item(news_item)

        page += 1  # Go to the next page
        
    print(f"SETN新聞處理完成")


# Run the asyncio event loop
asyncio.run(main())

print("SETN爬取完成")

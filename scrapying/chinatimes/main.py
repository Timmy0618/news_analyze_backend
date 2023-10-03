import asyncio
import aiohttp
import sqlite3
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.common.action_chains import ActionChains
import time
from datetime import datetime, timedelta
import pytz
import random
# Connect to SQLite database
conn = sqlite3.connect('news.db')
cursor = conn.cursor()

# Define the base URL and the target URL
BASE_URL = "https://www.chinatimes.com/"
TARGET_URL = "https://www.chinatimes.com/politic/total?page=2&chdtv"


async def fetch(url, session):
    """Fetch a URL using aiohttp."""
    async with session.get(url, headers=HEADERS) as response:
        return await response.text()


async def fetch_all(urls):
    """Fetch all URLs in the given list concurrently."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(url, session) for url in urls]
        return await asyncio.gather(*tasks)


def get_news_links_from_html(html_content):
    """Extracts news links and publish times from the HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Locate the div elements with class 'col'
    extracted_data = []
    for col_div in soup.find_all('div', class_='col'):
        # For each such div, find the h3 element with class 'title'
        title_tag = col_div.find('h3', class_='title')
        time_tag = col_div.find('time', datetime=True)

        if title_tag and time_tag:
            # Extract the text of the a element within the h3
            title = title_tag.find('a').get_text(strip=True)

            # Extract the href attribute of the a element
            href = title_tag.find('a')['href']

            # Extract the datetime attribute of the time element
            publish_time = time_tag['datetime']

            extracted_data.append((title, publish_time, href))

    return extracted_data


def slow_scroll_to_bottom(driver, scroll_pause_time=0.5):
    # Get current scroll position
    last_position = driver.execute_script("return window.pageYOffset;")

    while True:
        # Scroll down slowly
        # Adjust this value based on your needs
        driver.execute_script("window.scrollBy(0, 200);")
        # Wait for the page to load more content
        time.sleep(scroll_pause_time)
        # Check if we've reached the bottom yet
        current_position = driver.execute_script("return window.pageYOffset;")
        if current_position == last_position:
            break
        last_position = current_position


def click_next_page(driver):
    try:
        next_page_button = driver.find_element(
            By.CSS_SELECTOR, "li.page-item a.page-link")

        # Move to the button and click it
        actions = ActionChains(driver)
        actions.move_to_element(next_page_button).perform()

        # Wait a bit before clicking
        time.sleep(0.5)

        next_page_button.click()

        return True

    except NoSuchElementException:
        print("Reached the last page.")

        return False
    except ElementClickInterceptedException:
        driver.execute_script(
            "arguments[0].scrollIntoView(true);", next_page_button)
        time.sleep(2)
        next_page_button.click()

        return True

    # Wait a bit before loading the new page
    time.sleep(3)


def main():
    driver = webdriver.Chrome()

    # Use execute_cdp_cmd to modify the window.navigator object
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(window, 'navigator', {
                value: new Proxy(navigator, {
                    has: (target, key) => (key === 'webdriver' ? false : key in target),
                    get: (target, key) =>
                        key === 'webdriver'
                            ? undefined
                            : typeof target[key] === 'function'
                                ? target[key].bind(target)
                                : target[key]
                })
            });
        """
    })
    driver.get(TARGET_URL)

    taipei_tz = pytz.timezone('Asia/Taipei')
    seven_days_ago = datetime.now(taipei_tz) - timedelta(days=7)

    while True:
        # Wait for the page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "ul.vertical-list.list-style-none"))
        )

        # Random delay to mimic human behavior
        time.sleep(random.randint(5, 10))

        html_content = driver.page_source
        news_data = get_news_links_from_html(html_content)

        # Slowly scroll to the bottom of the page
        slow_scroll_to_bottom(driver)

        # Try to find the "next page" button and click it
        if not click_next_page(driver):
            break

    driver.quit()


main()
# Close database connection
conn.close()

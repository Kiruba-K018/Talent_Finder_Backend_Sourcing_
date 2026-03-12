import random
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from src.config.settings import get_settings
from src.observability.logging.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def build_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    if settings.scraper_headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    if settings.proxy_url:
        options.add_argument(f"--proxy-server={settings.proxy_url}")

    driver = uc.Chrome(options=options)
    driver.set_page_load_timeout(settings.scraper_page_timeout)
    return driver


def _human_delay() -> None:
    time.sleep(random.uniform(settings.scraper_min_delay, settings.scraper_max_delay))


def _scroll_page(driver: uc.Chrome) -> None:
    total_height = driver.execute_script("return document.body.scrollHeight")
    for pos in range(0, total_height, random.randint(200, 400)):
        driver.execute_script(f"window.scrollTo(0, {pos});")
        time.sleep(random.uniform(0.1, 0.4))


def inject_session_cookie(driver: uc.Chrome, cookie_value: str) -> None:
    driver.get("https://www.linkedin.com")
    driver.add_cookie({"name": "li_at", "value": cookie_value})
    driver.refresh()
    _human_delay()


def fetch_profile_html(driver: uc.Chrome, profile_url: str) -> str:
    driver.get(profile_url)
    _human_delay()
    _scroll_page(driver)
    _human_delay()
    return driver.page_source


def search_profiles(driver: uc.Chrome, query: str, max_results: int) -> list[str]:
    """
    Performs a Google site search for LinkedIn profiles.
    Returns a list of profile URLs.
    """
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    driver.get(search_url)
    _human_delay()

    soup = BeautifulSoup(driver.page_source, "lxml")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "linkedin.com/in/" in href:
            clean = href.split("&")[0].replace("/url?q=", "")
            if clean not in links:
                links.append(clean)
        if len(links) >= max_results:
            break

    logger.info("profiles_found", count=len(links), query=query)
    return links
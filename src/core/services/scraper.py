import random
import time

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.config.settings import get_settings
from src.observability.logging.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Global session storage - reuse authenticated driver instance
_authenticated_driver: uc.Chrome | None = None
_driver_cookies: list[dict] | None = None


def build_driver(headless: bool | None = None) -> uc.Chrome:
    # Use headless setting from config
    if headless is None:
        headless = settings.scraper_headless

    options = uc.ChromeOptions()
    if headless:
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

    # Set binary location from settings
    options.binary_location = settings.chrome_bin

    driver = uc.Chrome(options=options, browser_executable_path=settings.chrome_bin)
    driver.set_page_load_timeout(settings.scraper_page_timeout)
    return driver


def _human_delay() -> None:
    time.sleep(random.uniform(settings.scraper_min_delay, settings.scraper_max_delay))


def _scroll_page(driver: uc.Chrome) -> None:
    """
    Scroll page to trigger lazy loading of content sections.
    Important for LinkedIn profiles where experience/education load on demand.
    """
    try:
        total_height = driver.execute_script("return document.body.scrollHeight")
        current_pos = 0
        last_height = 0
        max_scrolls = 10
        scroll_count = 0

        while scroll_count < max_scrolls and current_pos < total_height:
            # Scroll down
            scroll_amount = min(random.randint(300, 500), total_height - current_pos)
            driver.execute_script(f"window.scrollTo(0, {current_pos + scroll_amount});")
            current_pos += scroll_amount
            time.sleep(random.uniform(0.3, 0.8))

            # Check if new content loaded
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height > last_height:
                logger.debug(f"New content loaded: {last_height} -> {new_height}")
                last_height = new_height
                total_height = max(total_height, new_height)

            scroll_count += 1

        # Final scroll to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(0.5, 1.0))

        logger.debug(
            f"Completed page scroll: {scroll_count} scrolls, final height: {total_height}"
        )
    except Exception as e:
        logger.debug(f"Error during page scroll: {e}")


def inject_session_cookie(
    driver: uc.Chrome, cookie_value: str, retries: int = 3
) -> bool:
    """
    Inject LinkedIn session cookie from stored value.
    This completely bypasses login and OTP verification.
    Includes retry logic for timeout resilience.

    Returns True if successful and user is authenticated, False otherwise.
    """
    if not cookie_value or not cookie_value.strip():
        logger.warning("No LinkedIn session cookie provided")
        return False

    last_error = None

    for attempt in range(retries):
        try:
            logger.debug(f"Session cookie injection attempt {attempt + 1}/{retries}")
            logger.info("Injecting session cookie...")

            # First, navigate to LinkedIn to set the domain context
            logger.debug("Navigating to LinkedIn to establish domain context...")

            try:
                # Increase timeout for initial navigation
                driver.set_page_load_timeout(45)
                driver.get("https://www.linkedin.com")
            except TimeoutException as e:
                logger.warning(
                    f"LinkedIn home page load timeout on attempt {attempt + 1} - may have partial content"
                )
                last_error = e

                # Even if timeout, we might have partial page - try to extract it
                try:
                    if "linkedin" in driver.current_url.lower():
                        logger.debug(
                            "Partially loaded LinkedIn - continuing with cookie injection"
                        )
                        # Proceed even with partial load
                    else:
                        if attempt < retries - 1:
                            wait_time = 2**attempt
                            logger.debug(f"Waiting {wait_time}s before retry...")
                            time.sleep(wait_time)
                        continue
                except Exception as e:
                    if attempt < retries - 1:
                        wait_time = 2**attempt
                        logger.debug(f"Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    continue

            _human_delay()

            # Check if already logged in (cookie may already exist)
            try:
                if "feed" in driver.current_url or "mynetwork" in driver.current_url:
                    logger.info("Already logged in! Cookie is valid.")
                    return True
            except Exception as e:
                logger.debug(f"Error occurred while checking login status: {e}")
                pass

            # Add the session cookie
            logger.debug("Adding li_at cookie to driver...")
            driver.add_cookie(
                {
                    "name": "li_at",
                    "value": cookie_value,
                    "domain": ".linkedin.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                    "sameSite": "Lax",
                }
            )

            logger.debug("Cookie added successfully - refreshing page...")
            try:
                driver.set_page_load_timeout(45)
                driver.refresh()
            except TimeoutException:
                logger.warning("Page refresh timeout - cookie may still be injected")
                # Continue anyway - cookie might be valid even if refresh times out

            _human_delay()

            # Verify authentication worked
            try:
                current_url = driver.current_url
                if (
                    "feed" in current_url
                    or "mynetwork" in current_url
                    or "search" in current_url
                ):
                    logger.info("Session cookie authentication successful!")
                    return True
                elif "login" in current_url.lower():
                    logger.warning("Cookie invalid or expired - redirected to login")
                    if attempt < retries - 1:
                        time.sleep(2**attempt)
                        continue
                else:
                    logger.info(f"Cookie injected (URL: {current_url})")
                    return True
            except Exception:
                logger.warning(
                    "Could not verify authentication status - assuming cookie was injected"
                )
                return True

        except Exception as e:
            last_error = e
            logger.debug(f"Failed on attempt {attempt + 1}: {str(e)}")

            if attempt < retries - 1:
                wait_time = 2**attempt
                logger.debug(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

    # All retries exhausted
    logger.warning(f"Failed to inject session cookie after {retries} attempts")
    logger.warning(f"Last error: {str(last_error)}")
    return False


def login_to_linkedin(driver: uc.Chrome, email: str, password: str) -> bool:
    """
    Attempt to log into LinkedIn using provided credentials.
    Critical for accessing LinkedIn search results directly.

    Returns True if login succeeded, False otherwise.
    """
    global _driver_cookies

    if not email or not password:
        logger.warning("Email or password not provided for LinkedIn login")
        return False

    try:
        logger.info("Navigating to LinkedIn login page...")
        driver.get("https://www.linkedin.com/login")
        time.sleep(3)

        wait = WebDriverWait(driver, 30)

        # Check if already logged in
        if "feed" in driver.current_url or "mynetwork" in driver.current_url:
            logger.info("Already logged in via saved session")
            _driver_cookies = driver.get_cookies()
            return True

        # Wait for and fill email field
        logger.info("Finding email field...")
        try:
            email_field = wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            email_field.clear()
            for char in email:
                email_field.send_keys(char)
                time.sleep(random.uniform(0.01, 0.05))
            time.sleep(1)
            logger.info("Email entered successfully")
        except TimeoutException:
            logger.error("Email field not found - page may not have loaded")
            # Try alternate email field selector
            try:
                email_field = driver.find_element(
                    By.CSS_SELECTOR, "input[type='text'][name='session_key']"
                )
                email_field.clear()
                email_field.send_keys(email)
                time.sleep(1)
                logger.info("Email entered via alternate selector")
            except Exception:
                logger.error("Could not find email field with any selector")
                return False

        # Wait for and fill password field
        logger.info("Finding password field...")
        try:
            password_field = wait.until(
                EC.presence_of_element_located((By.ID, "password"))
            )
            password_field.clear()
            for char in password:
                password_field.send_keys(char)
                time.sleep(random.uniform(0.01, 0.05))
            time.sleep(1)
            logger.info("Password entered successfully")
        except (TimeoutException, NoSuchElementException):
            logger.error("Password field not found")
            try:
                password_field = driver.find_element(
                    By.CSS_SELECTOR, "input[type='password'][name='session_password']"
                )
                password_field.send_keys(password)
                time.sleep(1)
                logger.info("Password entered via alternate selector")
            except Exception:
                logger.error("Could not find password field")
                return False

        # Submit login form
        logger.info("Submitting login form...")
        try:
            submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            submit_btn.click()
            logger.info("Login form submitted")
        except Exception:
            # Try form submission via Enter key
            password_field.submit()
            logger.info("Form submitted via Enter key")

        # Wait for login to complete
        time.sleep(4)

        # Check multiple URLs that indicate successful login
        max_attempts = 15
        for attempt in range(max_attempts):
            current_url = driver.current_url
            logger.debug(f"Login attempt {attempt + 1}/{max_attempts}: {current_url}")

            # Success indicators
            if any(
                x in current_url
                for x in ["feed", "mynetwork", "search", "inbox", "messaging"]
            ):
                logger.info(f"LinkedIn login successful! URL: {current_url}")
                _driver_cookies = driver.get_cookies()
                time.sleep(2)  # Extra wait to ensure session is stable
                return True

            # Checkpoint/security challenge - may require manual OTP entry
            if "checkpoint" in current_url or "challenge" in current_url:
                logger.warning(
                    "LinkedIn security checkpoint detected - may require email OTP verification"
                )
                logger.warning(
                    "Check your email for LinkedIn verification code and enter it in the browser window"
                )
                logger.info("Waiting for verification (up to 10 minutes)...")

                # Wait up to 10 minutes for manual OTP entry
                for attempt in range(300):  # 300 * 2 = 600 seconds = 10 minutes
                    time.sleep(2)
                    current_url = driver.current_url

                    # Check if checkpoint is resolved
                    if (
                        "checkpoint" not in current_url
                        and "challenge" not in current_url
                    ):
                        logger.info(
                            f"Checkpoint verified! Continuing after {attempt * 2} seconds"
                        )
                        _driver_cookies = driver.get_cookies()
                        time.sleep(2)
                        return True

                    # Progress indicator every 30 seconds
                    if attempt % 15 == 0 and attempt > 0:
                        remaining_min = (300 - attempt) * 2 / 60
                        logger.info(
                            f"Still waiting... ({remaining_min:.1f} minutes remaining)"
                        )

                logger.error(
                    "Checkpoint verification timeout (10 minutes) - login failed"
                )
                return False

            time.sleep(2)

        logger.error(f"Login timeout - final URL: {driver.current_url}")
        return False

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        import traceback

        logger.debug(traceback.format_exc())
        return False


def get_authenticated_driver() -> uc.Chrome:
    """
    Get or create an authenticated driver instance.
    Authentication strategy for LinkedIn search (in priority order):
    1. Reuse existing authenticated driver if available
    2. Try injecting stored SESSION COOKIE (fastest, bypasses OTP)
    3. Try auto-login with email/password (slower, may trigger OTP)
    4. Return unauthenticated (will fail on LinkedIn search)
    """
    global _authenticated_driver

    # Reuse existing authenticated driver
    if _authenticated_driver is not None:
        try:
            _ = _authenticated_driver.current_url
            logger.info("Reusing authenticated driver session")
            return _authenticated_driver
        except Exception:
            logger.warning("Existing driver is dead - creating new one")
            _authenticated_driver = None

    driver = build_driver()

    # Debug: Log authentication options
    cookie_configured = bool(
        settings.linkedin_session_cookie and settings.linkedin_session_cookie.strip()
    )
    email_configured = bool(settings.linkedin_email and settings.linkedin_email.strip())
    password_configured = bool(
        settings.linkedin_password and settings.linkedin_password.strip()
    )
    logger.debug(
        f"LinkedIn auth options: cookie={cookie_configured}, email={email_configured}, password={password_configured}"
    )

    if not (cookie_configured or (email_configured and password_configured)):
        logger.error("No LinkedIn credentials configured!")
        logger.error(
            "To enable LinkedIn sourcing, configure ONE of the following in your .env file:"
        )
        logger.error(
            "  Option 1 (Recommended): LINKEDIN_SESSION_COOKIE=<your_li_at_cookie>"
        )
        logger.error(
            "  Option 2 (With OTP): LINKEDIN_EMAIL=<your_email> and LINKEDIN_PASSWORD=<your_password>"
        )
        logger.error("")
        logger.error("To get your session cookie:")
        logger.error("  1. Log in to LinkedIn in your browser")
        logger.error("  2. Open DevTools (F12) → Application → Cookies → linkedin.com")
        logger.error("  3. Find 'li_at' cookie and copy its value")
        logger.error("  4. Add to .env: LINKEDIN_SESSION_COOKIE=<value>")
        logger.error("  5. Restart the sourcing service")
        raise RuntimeError(
            "No LinkedIn credentials configured - see logs for setup instructions"
        )

    # PRIORITY 1: Try session cookie FIRST (bypasses OTP completely)
    if cookie_configured:
        logger.info(
            "Attempting session cookie authentication (fastest, bypasses OTP)..."
        )
        if inject_session_cookie(driver, settings.linkedin_session_cookie):
            _authenticated_driver = driver
            logger.info("Successfully authenticated via session cookie!")
            return driver
        else:
            logger.warning(
                "Session cookie authentication failed - trying email/password..."
            )

    # PRIORITY 2: Fall back to email/password (may trigger OTP)
    if email_configured and password_configured:
        logger.info("Attempting email/password login (may trigger OTP checkpoint)...")
        if login_to_linkedin(
            driver, settings.linkedin_email, settings.linkedin_password
        ):
            _authenticated_driver = driver
            logger.info("Successfully authenticated via email/password")
            return driver
        else:
            logger.error(
                "LinkedIn login failed - both authentication methods exhausted"
            )
    else:
        logger.error(
            "No LinkedIn credentials configured (LINKEDIN_EMAIL + LINKEDIN_PASSWORD required)"
        )

    # FALLBACK: Return unauthenticated
    logger.error("No working authentication found - search will likely fail")
    _authenticated_driver = driver
    return driver


def _wait_for_profile_content(driver: uc.Chrome, timeout: int = 15) -> bool:
    """
    Wait for actual profile content to be rendered by JavaScript.
    Checks for experience/education sections with actual text content.

    Returns True if content found, False if timeout.
    """
    try:
        wait = WebDriverWait(driver, timeout)

        # Wait for profile header
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        logger.debug("Profile header rendered")

        # Wait for at least one list item with meaningful content (experience/education/projects)
        # These should have actual text, not empty elements
        def has_content_items(d):
            items = d.find_elements(By.CSS_SELECTOR, "li[class*='artdeco-list__item']")
            for item in items[:10]:
                try:
                    # Use Selenium WebElement.text, not get_text() from BeautifulSoup
                    if len(item.text.strip()) > 20:
                        return True
                except Exception:
                    continue
            return False

        wait.until(has_content_items)
        logger.debug("Profile content sections rendered with text")

        return True
    except Exception as e:
        logger.warning(f"Could not wait for full content: {e}")
        return False


def fetch_profile_html(driver: uc.Chrome, profile_url: str, retries: int = 3) -> str:
    """
    Fetch LinkedIn profile HTML with retry logic and JavaScript rendering waits.

    This function:
    1. Waits for page to load initially
    2. Waits for profile content to be rendered by JavaScript
    3. Scrolls to trigger lazy-loaded sections
    4. Waits for all content to be visible
    5. Captures final HTML after all JS execution

    Args:
        driver: Selenium WebDriver instance
        profile_url: LinkedIn profile URL to fetch
        retries: Number of retry attempts if page load fails

    Returns:
        HTML source code with fully rendered content
    """
    last_error = None

    for attempt in range(retries):
        try:
            logger.debug(
                f"Fetching profile (attempt {attempt + 1}/{retries}): {profile_url}"
            )

            # Increase timeout for individual profile loads
            driver.set_page_load_timeout(45)

            try:
                driver.get(profile_url)
            except TimeoutException as e:
                logger.warning(f"Page load timeout on attempt {attempt + 1}")
                last_error = e

                if attempt < retries - 1:
                    wait_time = 2**attempt
                    logger.debug(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                continue

            logger.debug("Page navigation completed, waiting for content render...")
            _human_delay()

            # Step 1: Wait for initial profile structure
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "h1"))
                )
                logger.debug("Profile header present")
            except Exception as e:
                logger.warning(f"Could not find profile header: {e}")
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                continue

            # Step 2: Scroll to trigger lazy loading
            logger.debug("Scrolling to trigger content loading...")
            _scroll_page(driver)
            _human_delay()

            # Step 3: Wait for actual content to be rendered (JavaScript execution)
            if not _wait_for_profile_content(driver, timeout=20):
                logger.warning(
                    f"Profile content did not render on attempt {attempt + 1}"
                )
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                continue

            # Step 4: Scroll again to ensure all lazy-loaded content is in view
            _scroll_page(driver)
            _human_delay()

            # Step 5: Final wait for any remaining async content
            time.sleep(random.uniform(2, 3))

            # Capture final HTML
            html = driver.page_source
            if not html or len(html) < 1000:
                logger.warning(
                    f"HTML too small on attempt {attempt + 1}: {len(html)} bytes"
                )
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                continue

            logger.debug(
                f"Successfully retrieved {len(html)} bytes of fully-rendered HTML"
            )
            return html

        except Exception as e:
            last_error = e
            logger.debug(f"Error on attempt {attempt + 1}: {str(e)}")

            if attempt < retries - 1:
                wait_time = 2**attempt
                logger.debug(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

    logger.error(f"Failed to fetch profile after {retries} attempts: {profile_url}")
    if last_error:
        logger.error(f"Last error: {str(last_error)}")

    return ""


def extract_from_chameleon_cards(soup: BeautifulSoup, max_results: int) -> list[str]:
    """Extract profiles from LinkedIn search results using chameleon card elements."""
    links = []
    profile_cards = soup.find_all(
        "div", {"data-chameleon-result-urn": lambda x: x and "urn:li:member" in x}
    )
    logger.debug(f"Chameleon cards found: {len(profile_cards)}")

    for card in profile_cards:
        if len(links) >= max_results:
            break
        profile_link = card.find("a", href=lambda x: x and "/in/" in x)
        if profile_link and profile_link.get("href"):
            href = profile_link.get("href", "")
            clean = href.split("?")[0].split("#")[0]
            if clean.startswith("http") and clean not in links:
                links.append(clean)
                logger.debug(f"Chameleon extraction: {clean}")

    return links


def extract_from_generic_links(soup: BeautifulSoup, max_results: int) -> list[str]:
    """Extract profiles from all LinkedIn profile links in the page."""
    links = []
    # Find all anchor tags with LinkedIn profile URLs
    for a in soup.find_all("a", href=lambda x: x and "/in/" in x):
        if len(links) >= max_results:
            break
        href = a.get("href", "")
        clean = href.split("?")[0].split("#")[0]

        if (
            clean.startswith("http")
            and clean not in links
            and "/search" not in clean
            and "/pulse" not in clean
            and "/company/" not in clean
        ):
            links.append(clean)
            logger.debug(f"Generic extraction: {clean}")

    return links


def extract_from_search_container(soup: BeautifulSoup, max_results: int) -> list[str]:
    """Extract profiles from within search results container."""
    links = []
    # Find search results container
    search_container = soup.find("div", class_="search-results-container")
    if not search_container:
        logger.debug("Search results container not found")
        return links

    for a in search_container.find_all("a", href=lambda x: x and "/in/" in x):
        if len(links) >= max_results:
            break
        href = a.get("href", "")
        clean = href.split("?")[0].split("#")[0]

        if (
            clean.startswith("http")
            and clean not in links
            and "/search" not in clean
            and "/pulse" not in clean
            and "/company/" not in clean
        ):
            links.append(clean)
            logger.debug(f"Search container extraction: {clean}")

    return links


def search_profiles(
    driver: uc.Chrome, query: str, max_results: int, location: str = "India"
) -> list[str]:
    """
    Performs a direct LinkedIn search for profiles.
    REQUIRES authenticated driver (must be logged in).

    Args:
        driver: Authenticated Chrome driver instance
        query: Search keywords (e.g., "Python Developer")
        max_results: Maximum profiles to return
        location: Location filter (default: India)

    Returns:
        List of LinkedIn profile URLs
    """
    links = []

    # Verify we're logged in (check if we're at LinkedIn domain)
    try:
        driver.get("https://www.linkedin.com/feed")
        time.sleep(2)
        if "login" in driver.current_url.lower():
            logger.error(
                "Not authenticated - redirected to login page. Cannot perform search."
            )
            return []
    except Exception as e:
        logger.error(f"Error verifying authentication: {str(e)}")
        return []

    # Map location to LinkedIn geo code
    location_codes = {
        "India": "102713980",
        "USA": "103644243",
        "UK": "101165590",
        "Canada": "102393587",
    }
    geo_code = location_codes.get(location, location_codes["India"])

    # Build direct LinkedIn search URL with filters
    # Format: https://www.linkedin.com/search/results/people/?keywords=python&geoUrn=LIST%28102713980%29
    search_url = (
        f"https://www.linkedin.com/search/results/people/?"
        f"keywords={query.replace(' ', '%20')}&"
        f"geoUrn=LIST%28{geo_code}%29&"
        f"serviceCategory=LIST%28602%29"  # Software Development
    )

    logger.info(f"Searching LinkedIn for: {query} (Location: {location})")
    logger.debug(f"Search URL: {search_url}")

    try:
        driver.get(search_url)
        time.sleep(3)  # Wait for page load

        # Check for login redirect
        if "login" in driver.current_url.lower():
            logger.error("Redirected to login - session may have expired")
            return []

        # Wait for dynamic content - LinkedIn renders results via JavaScript
        logger.info("Waiting for search results to render...")

        try:
            wait = WebDriverWait(driver, 90)
            # Try waiting for profile cards first
            wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'div[data-chameleon-result-urn*="urn:li:member"]')
                )
            )
            logger.info("Profile card elements found")

        except TimeoutException:
            logger.debug(
                "Profile cards not found with data-chameleon-result-urn selector - trying alternatives..."
            )
            try:
                # Alternative: Wait for search results container
                wait.until(
                    EC.presence_of_element_located(
                        (By.CLASS_NAME, "search-results-container")
                    )
                )
                logger.debug("Search results container found - will parse page")

            except TimeoutException:
                logger.debug(
                    "Search results container not found - trying to load any search-related content..."
                )
                try:
                    wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "a[href*='/in/']")
                        )
                    )
                    logger.debug("Profile links found in page")

                except TimeoutException:
                    logger.warning(
                        "Timeout waiting for any search results - page may not have loaded"
                    )

        # Scroll to load more profiles
        for scroll_count in range(5):
            logger.debug(f"Scrolling page {scroll_count + 1}/5...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1.5, 2.5))
            if len(links) >= max_results:
                break

        time.sleep(2)

        # Strategy 1: Parse HTML with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "lxml")
        logger.debug(f"Page source length: {len(driver.page_source)} characters")

        # Try multiple extraction strategies with priority order
        extraction_strategies = [
            (
                "Profile cards with data-chameleon-result-urn",
                lambda: extract_from_chameleon_cards(soup, max_results - len(links)),
            ),
            (
                "Generic LinkedIn profile links",
                lambda: extract_from_generic_links(soup, max_results - len(links)),
            ),
            (
                "Search result container links",
                lambda: extract_from_search_container(soup, max_results - len(links)),
            ),
        ]

        for strategy_name, extraction_fn in extraction_strategies:
            if len(links) >= max_results:
                break
            try:
                logger.debug(f"Attempting: {strategy_name}")
                new_links = extraction_fn()
                if new_links:
                    logger.info(
                        f"Found {len(new_links)} profiles using: {strategy_name}"
                    )
                    links.extend(new_links)
                    break
            except Exception as e:
                logger.debug(f"Strategy failed ({strategy_name}): {str(e)}")

        # Strategy 2: Use JavaScript to extract any profile links (fallback)
        if len(links) == 0:
            logger.info(
                "No profiles found with parsing strategies - trying JavaScript extraction..."
            )
            try:
                js_links = driver.execute_script(
                    """
                    return Array.from(document.querySelectorAll('a[href*="/in/"]'))
                        .map(a => a.href)
                        .filter((href, index, self) => self.indexOf(href) === index && !href.includes('/search') && !href.includes('/pulse') && !href.includes('/company/'))
                        .slice(0, arguments[0]);
                """,
                    max_results,
                )

                links = js_links if js_links else []
                logger.info(f"JavaScript extraction found {len(links)} profiles")
            except Exception as e:
                logger.warning(f"JavaScript extraction failed: {str(e)}")

        logger.info(f"profiles_found: count={len(links)}")
        if len(links) > 0:
            logger.info(f"Successfully found {len(links)} profiles on LinkedIn")
            logger.debug(f"First 3 profiles: {links[:3]}")
        else:
            logger.warning(f"No profiles found for: {query}")

            # Debug: Check for error messages or empty results
            if any(
                x in driver.page_source.lower()
                for x in ["no results", "no people", "no matches"]
            ):
                logger.warning("LinkedIn search returned no results for this query")
            else:
                logger.warning(
                    "Could not extract profiles - checking page structure..."
                )

                # Try to understand what's on the page
                try:
                    # Check if profile card elements exist at all
                    card_elements = soup.find_all(
                        "div",
                        {
                            "data-chameleon-result-urn": lambda x: (
                                x and "urn:li:member" in x
                            )
                        },
                    )
                    logger.debug(f"Profile card elements found: {len(card_elements)}")

                    # Also check for generic profile links
                    all_profile_links = soup.find_all(
                        "a", href=lambda x: x and "/in/" in x
                    )
                    logger.debug(f"Profile links found: {len(all_profile_links)}")
                except Exception as e:
                    logger.debug(f"Error during debug extraction: {str(e)}")

        return links

    except Exception as e:
        logger.error(f"LinkedIn search error: {str(e)}")
        import traceback

        logger.debug(traceback.format_exc())
        return []

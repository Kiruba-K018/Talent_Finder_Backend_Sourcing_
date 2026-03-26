"""Playwright-based scraper for PostJobFree resume pages."""

import asyncio

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.config.settings import get_settings
from src.observability.logging.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Global browser instance - reuse across requests
_browser: Browser | None = None
_context: BrowserContext | None = None

# Common location typo mappings for SerpAPI
LOCATION_TYPO_MAP = {
    "inida": "India",
    "indai": "India",
    "india": "India",
    "us": "United States",
    "usa": "United States",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "canada": "Canada",
    "australia": "Australia",
}

# Valid SerpAPI locations (canonical forms)
VALID_LOCATIONS = {
    "India",
    "United States",
    "United Kingdom",
    "Canada",
    "Australia",
    "Germany",
    "France",
    "Japan",
    "Singapore",
}


def validate_sourcing_params(query: str, location: str = "India") -> tuple[str, str]:
    """
    Validate and sanitize sourcing parameters for SerpAPI.

    Fixes common typos in location and ensures parameters are production-grade.

    Args:
        query: Search query (e.g., "python developer")
        location: Location filter (e.g., "India")

    Returns:
        Tuple of (validated_query, validated_location)

    Raises:
        ValueError: If parameters are invalid or cannot be fixed
    """
    # Trim whitespace
    query = query.strip() if query else ""
    location = location.strip() if location else "India"

    # Validate query
    if not query:
        raise ValueError("Search query cannot be empty")

    if len(query) > 500:
        raise ValueError(f"Search query too long: {len(query)} characters (max 500)")

    # Fix location typos - case-insensitive mapping
    location_lower = location.lower()

    # Check if it's a known typo and fix it
    if location_lower in LOCATION_TYPO_MAP:
        corrected_location = LOCATION_TYPO_MAP[location_lower]
        logger.info(
            "location_typo_corrected",
            original=location,
            corrected=corrected_location,
        )
        location = corrected_location
    elif location not in VALID_LOCATIONS:
        # If not in valid list and not a known typo, log and use default
        logger.warning(
            "location_not_in_valid_list",
            location=location,
            valid_locations=list(VALID_LOCATIONS),
        )
        location = "India"  # Safe default

    logger.debug(
        "sourcing_params_validated",
        query=query,
        location=location,
    )

    return query, location


async def _get_browser() -> Browser:
    """Get or create a browser instance."""
    global _browser
    if _browser is None:
        playwright = await async_playwright().start()
        _browser = await playwright.chromium.launch(
            headless=settings.playwright_headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
    return _browser


async def _get_context() -> BrowserContext:
    """Get or create a browser context."""
    global _context
    if _context is None:
        browser = await _get_browser()
        _context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
    return _context


async def scrape_resume_page(resume_url: str) -> str | None:
    """
    Scrape resume text from a PostJobFree resume page.

    Args:
        resume_url: URL to the PostJobFree resume page

    Returns:
        Raw resume text extracted from the page, or None if scraping fails
    """
    page: Page | None = None
    try:
        context = await _get_context()
        page = await context.new_page()

        # Navigate to the resume page with timeout
        logger.debug("scraping_resume_page_start", url=resume_url)
        await page.goto(
            resume_url,
            wait_until="networkidle",
            timeout=settings.playwright_timeout,
        )

        # Wait for page to fully load - important for JavaScript-heavy pages
        await asyncio.sleep(2)  # Wait for content to fully load

        target_selector = "div.normalText"

        try:
            logger.debug("waiting_for_normalText_element", url=resume_url)
            await page.wait_for_selector(target_selector, timeout=15000)
        except Exception as e:
            logger.warning(
                "normalText_element_not_found_after_wait",
                url=resume_url,
                error=str(e),
            )
            return None

        # Check how many elements matched the selector
        resume_elements = page.locator(target_selector)
        element_count = await resume_elements.count()

        logger.debug("normalText_elements_found", count=element_count, url=resume_url)

        # Should be exactly 1 element for an individual resume page
        if element_count != 1:
            logger.warning(
                "unexpected_element_count_on_resume_page",
                url=resume_url,
                element_count=element_count,
                expected=1,
            )
            if element_count == 0:
                logger.error("no_normaltext_element_found", url=resume_url)
            else:
                logger.error(
                    "multiple_normaltext_elements_found",
                    url=resume_url,
                    count=element_count,
                )
            return None

        # Safe to use .first since we confirmed count == 1
        try:
            full_text = await resume_elements.first.inner_text(timeout=5000)
            full_html = await resume_elements.first.inner_html(timeout=5000)

            if not full_html or not full_html.strip():
                logger.warning("resume_html_empty", url=resume_url)
                return None

            logger.info(
                "successfully_extracted_resume_content",
                url=resume_url,
                length=len(full_text),
            )

            return {"html": full_html, "text": full_text}
        except Exception as e:
            logger.error(
                "failed_to_extract_html_or_text",
                url=resume_url,
                error=str(e),
            )
            return None
    finally:
        if page:
            await page.close()


async def search_postjobfree(
    query: str, location: str = "India"
) -> tuple[list[dict], dict | None]:
    """
    Search PostJobFree for candidates by directly scraping the website.

    Uses the URL template: https://www.postjobfree.com/resumes?q={keywords}&l={location}&radius=25
    Parses the HTML to extract individual resume links from search results.

    Args:
        query: Search query (e.g., "software developer python fastapi")
        location: Location filter (default: "India")

    Returns:
        Tuple of (results_list, error_dict):
        - results_list: List of candidate result dicts with 'title', 'link', 'snippet' keys
        - error_dict: None if successful, or dict with error details if parsing/scraping fails
    """
    page: Page | None = None
    try:
        # Step 1: Validate and sanitize parameters
        try:
            validated_query, validated_location = validate_sourcing_params(
                query, location
            )
        except ValueError as e:
            error_response = {
                "status_code": 400,
                "error": "INVALID_PARAMETERS",
                "error_message": str(e),
                "query": query,
                "location": location,
            }
            logger.error(
                "failed_postjobfree_search",
                query=query,
                location=location,
                error_detail=str(e),
                error_code="INVALID_PARAMETERS",
            )
            return [], error_response

        # Step 2: Build search URL with template
        # Replace spaces with + for URL encoding
        keywords = validated_query.replace(" ", "+")
        search_url = f"https://www.postjobfree.com/resumes?q={keywords}&l={validated_location}&radius=25"

        logger.info(
            "searching_postjobfree_website",
            query=validated_query,
            location=validated_location,
            search_url=search_url,
        )

        # Step 3: Fetch and parse search results page
        context = await _get_context()
        page = await context.new_page()

        try:
            await page.goto(
                search_url,
                wait_until="networkidle",
                timeout=settings.playwright_timeout,
            )
            logger.debug("postjobfree_search_page_loaded", search_url=search_url)
        except Exception as e:
            error_response = {
                "status_code": 500,
                "error": "NAVIGATION_FAILED",
                "error_message": f"Failed to navigate to {search_url}: {str(e)}",
                "query": validated_query,
                "location": validated_location,
            }
            logger.error(
                "failed_postjobfree_search",
                search_url=search_url,
                error_detail=f"Navigation failed: {str(e)}",
                error_code="NAVIGATION_FAILED",
            )
            return [], error_response

        # Wait for page to fully load
        await asyncio.sleep(2)

        # Step 4: Extract resume links from search results
        # Results are in div.snippetPadding elements within a div[style*="overflow-wrap:break-word"]
        # Each snippetPadding has: <h3 class="itemTitle"><a href="/resume/{id}/{slug}">Title</a></h3>

        results = []

        try:
            # Find all resume cards on the page
            resume_cards = page.locator("div.snippetPadding")
            card_count = await resume_cards.count()

            logger.debug(
                "resume_cards_found_on_search_results",
                count=card_count,
                search_url=search_url,
            )

            if card_count == 0:
                logger.warning(
                    "no_resume_cards_found_on_postjobfree",
                    search_url=search_url,
                    location=validated_location,
                    query=validated_query,
                )
                return [], None

            # Iterate through each resume card and extract data
            for i in range(card_count):
                try:
                    card = resume_cards.nth(i)

                    # Extract resume link from <h3 class="itemTitle"><a href="...">
                    title_element = card.locator("h3.itemTitle a").first
                    href = await title_element.get_attribute("href")
                    title_text = await title_element.inner_text()

                    if not href:
                        logger.debug("skipping_card_no_href", card_index=i)
                        continue

                    # Convert relative URL to absolute
                    if not href.startswith("http"):
                        href = f"https://www.postjobfree.com{href}"

                    # Extract location snippet from <span class="colorLocation">
                    location_element = card.locator("span.colorLocation").first
                    location_snippet = ""
                    try:
                        location_snippet = await location_element.inner_text()
                    except Exception:
                        location_snippet = validated_location

                    # Extract resume snippet from div.normalText (text preview)
                    snippet_element = card.locator("div.normalText").first
                    snippet = ""
                    try:
                        snippet = await snippet_element.inner_text()
                    except Exception:
                        snippet = ""

                    # Extract date from <span class="colorDate">
                    date_element = card.locator("span.colorDate").first
                    date_posted = ""
                    try:
                        date_posted = await date_element.inner_text()
                    except Exception:
                        date_posted = ""

                    # Build result object matching SerpAPI format for backward compatibility
                    result = {
                        "title": title_text.strip(),
                        "link": href,
                        "snippet": snippet.strip(),
                        "position": i + 1,
                        "location": location_snippet.strip(),
                        "date_posted": date_posted.strip(),
                    }

                    results.append(result)

                    logger.debug(
                        "extracted_resume_card",
                        card_index=i,
                        title=title_text[:50],
                        href=href,
                        location=location_snippet,
                    )

                except Exception as e:
                    logger.warning(
                        "failed_to_extract_resume_card",
                        card_index=i,
                        search_url=search_url,
                        error=str(e),
                    )
                    continue

            logger.info(
                "postjobfree_search_results",
                count=len(results),
                query=validated_query,
                location=validated_location,
                search_url=search_url,
            )

            return results, None

        except Exception as e:
            error_response = {
                "status_code": 500,
                "error": "PARSING_FAILED",
                "error_message": f"Failed to parse search results: {str(e)}",
                "query": validated_query,
                "location": validated_location,
            }
            logger.error(
                "failed_postjobfree_search",
                search_url=search_url,
                error_detail=f"Parsing failed: {str(e)}",
                error_code="PARSING_FAILED",
                exception_type=type(e).__name__,
            )
            return [], error_response

    except Exception as e:
        error_dict = {
            "status_code": 500,
            "error": "INTERNAL_ERROR",
            "error_message": str(e),
            "query": query,
            "location": location,
        }
        logger.error(
            "failed_postjobfree_search",
            query=query,
            location=location,
            error_detail=str(e),
            error_code="INTERNAL_ERROR",
            exception_type=type(e).__name__,
        )
        return [], error_dict
    finally:
        if page:
            await page.close()


async def close_browser() -> None:
    """Close the global browser instance."""
    global _browser, _context
    try:
        if _context:
            await _context.close()
            _context = None
        if _browser:
            await _browser.close()
            _browser = None
        logger.info("browser_closed")
    except Exception as e:
        logger.error("error_closing_browser", error=str(e))

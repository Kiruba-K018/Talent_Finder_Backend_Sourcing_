from bs4 import BeautifulSoup, Tag
from src.observability.logging.logger import get_logger

logger = get_logger(__name__)


def _text(tag: Tag | None) -> str:
    return tag.get_text(strip=True) if tag else ""


def parse_name(soup: BeautifulSoup) -> str:
    for selector in ["h1.text-heading-xlarge", "div.ph5.pb5 h1"]:
        tag = soup.select_one(selector)
        if tag:
            return _text(tag)
    return ""


def parse_title(soup: BeautifulSoup) -> str:
    tag = soup.select_one("div.text-body-medium")
    return _text(tag)


def parse_location(soup: BeautifulSoup) -> str:
    tag = soup.select_one("span.text-body-small.inline")
    return _text(tag)


def parse_summary(soup: BeautifulSoup) -> str:
    for selector in ["section#about", "div.display-flex.ph5.pv3"]:
        tag = soup.select_one(selector)
        if tag:
            return _text(tag)
    return ""


def parse_experience(soup: BeautifulSoup) -> list[dict]:
    entries = []
    section = soup.select_one("section#experience")
    if not section:
        return entries
    for item in section.select("li.artdeco-list__item"):
        company = _text(item.select_one(".t-14.t-normal")) or ""
        role    = _text(item.select_one(".t-bold span")) or ""
        dates   = item.select(".t-14.t-normal.t-black--light span[aria-hidden='true']")
        start   = _text(dates[0]) if len(dates) > 0 else ""
        end     = _text(dates[1]) if len(dates) > 1 else "Present"
        entries.append({
            "company_name": company,
            "role": role,
            "start_date": start,
            "end_date": end,
            "technologies": [],   # enriched downstream if NLP is added
        })
    return entries


def parse_skills(soup: BeautifulSoup) -> list[str]:
    section = soup.select_one("section#skills")
    if not section:
        return []
    return [_text(tag) for tag in section.select("span.skill-name") if _text(tag)]


def parse_education(soup: BeautifulSoup) -> list[dict]:
    entries = []
    section = soup.select_one("section#education")
    if not section:
        return entries
    for item in section.select("li.artdeco-list__item"):
        entries.append({
            "institution": _text(item.select_one(".t-bold span")),
            "degree": _text(item.select_one(".t-14.t-normal")),
            "field": "",
            "graduation_year": "",
        })
    return entries


def parse_certifications(soup: BeautifulSoup) -> list[str]:
    section = soup.select_one("section#licenses_and_certifications")
    if not section:
        return []
    return [_text(t) for t in section.select(".t-bold span") if _text(t)]


def parse_contact(soup: BeautifulSoup) -> tuple[str, str]:
    email = ""
    phone = ""
    for a in soup.select("a[href^='mailto:']"):
        email = a["href"].replace("mailto:", "").strip()
        break
    for a in soup.select("a[href^='tel:']"):
        phone = a["href"].replace("tel:", "").strip()
        break
    return email, phone


def parse_profile(html: str, profile_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    email, phone = parse_contact(soup)
    skills = parse_skills(soup)

    return {
        "name":            parse_name(soup),
        "email":           email,
        "phone":           phone,
        "location":        parse_location(soup),
        "title":           parse_title(soup),
        "summary":         parse_summary(soup),
        "hard_skills":     skills,
        "soft_skills":     [],
        "experience":      parse_experience(soup),
        "education":       parse_education(soup),
        "certifications":  parse_certifications(soup),
        "projects":        [],
        "profile_url":     profile_url,
        "source_platform": "linkedin",
    }
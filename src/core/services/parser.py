"""
Improved LinkedIn profile parser focusing on quality over quantity.
This version is much more selective and avoids noise from the page.
"""

import re

from bs4 import BeautifulSoup, Tag

from src.observability.logging.logger import get_logger

logger = get_logger(__name__)


def _text(tag: Tag | None) -> str:
    return tag.get_text(strip=True) if tag else ""


def _extract_name_from_url(soup: BeautifulSoup) -> str:
    """Extract name from LinkedIn profile URL."""
    try:
        # Look for LinkedIn profile URL in meta tags
        for meta in soup.find_all("meta"):
            content = meta.get("content", "")
            if "linkedin.com/in/" in content:
                # Extract username from URL
                match = re.search(r"linkedin\.com/in/([a-z0-9\-]+)", content)
                if match:
                    username = match.group(1)
                    # Clean up username: replace hyphens with spaces, remove trailing numbers
                    name = username.replace("-", " ")
                    # Remove trailing numbers (like -123 suffix)
                    name = re.sub(r"\s+\d+$", "", name)
                    if name:
                        return name.title()

        # Look for profile URL in canonical link
        canonical = soup.find("link", {"rel": "canonical"})
        if canonical:
            url = canonical.get("href", "")
            if "linkedin.com/in/" in url:
                match = re.search(r"linkedin\.com/in/([a-z0-9\-]+)", url)
                if match:
                    username = match.group(1)
                    name = username.replace("-", " ")
                    name = re.sub(r"\s+\d+$", "", name)
                    if name:
                        return name.title()

        # Look for any link with LinkedIn profile URL
        for link in soup.find_all("a"):
            href = link.get("href", "")
            if "linkedin.com/in/" in href:
                match = re.search(r"linkedin\.com/in/([a-z0-9\-]+)", href)
                if match:
                    username = match.group(1)
                    name = username.replace("-", " ")
                    name = re.sub(r"\s+\d+$", "", name)
                    if name:
                        return name.title()
    except Exception as e:
        logger.debug(f"Error extracting name from URL: {str(e)}")

    return ""


def parse_name(soup: BeautifulSoup) -> str:
    """Extract name from profile header - with multiple fallback strategies."""

    # Strategy 1 (PRIMARY): Extract from LinkedIn profile URL
    name_from_url = _extract_name_from_url(soup)
    if name_from_url:
        logger.debug(f"Extracted name from URL: {name_from_url}")
        return name_from_url

    # Strategy 2: Look for h1 tag in profile header
    for h1 in soup.find_all("h1"):
        name = _text(h1).strip()
        if (
            name
            and len(name) > 1
            and not any(
                x in name.lower()
                for x in ["follow", "message", "connect", "open to", "looking"]
            )
            and len(name.split()) <= 5
        ):
            return name

    # Strategy 3: Look for text near LinkedIn title (usually appears after title in header)
    title_section = soup.find(
        "div", {"class": lambda x: x and "pv-text-details__left-panel" in (x or "")}
    )
    if title_section:
        # Get all text, split by newline, first non-empty line should be name
        lines = [
            line.strip() for line in _text(title_section).split("\n") if line.strip()
        ]
        if lines and len(lines[0].split()) <= 5:
            return lines[0]

    # Strategy 4: Look for data attributes that might contain name
    for elem in soup.find_all(attrs={"data-test": True}):
        if "name" in (elem.get("data-test") or "").lower():
            name = _text(elem).strip()
            if name and len(name) > 1 and len(name.split()) <= 5:
                return name

    # Strategy 5: Look in meta tags (some sites put it there)
    meta_name = soup.find("meta", {"property": "og:title"})
    if meta_name:
        name = _text(meta_name.get("content", "")).strip()
        if name and len(name) > 1:
            # Extract just the name part (may have " | LinkedIn" appended)
            name = name.split("|")[0].strip()
            if len(name.split()) <= 5:
                return name

    # Strategy 6: Look for any span or div with 'artdeco-inline-feedback-button' or similar in profile header
    header = soup.find("header")
    if header:
        for text_elem in header.find_all(["span", "div"]):
            name = _text(text_elem).strip()
            if (
                name
                and len(name) > 1
                and 1 <= len(name.split()) <= 5
                and not any(
                    x in name.lower()
                    for x in [
                        "follow",
                        "message",
                        "connect",
                        "open to",
                        "looking",
                        "download",
                        "share",
                    ]
                )
            ):
                return name

    logger.debug("Could not extract candidate name from profile")
    return ""


def parse_title(soup: BeautifulSoup) -> str:
    """Extract current job title - multiple strategies."""

    # Strategy 1: Look for headline in header (usually 2nd line after name)
    header = soup.find("header")
    if header:
        header_text = _text(header)
        lines = [line.strip() for line in header_text.split("\n") if line.strip()]
        # Skip first line (name), second line is often title
        if len(lines) >= 2:
            potential_title = lines[1]
            if (
                len(potential_title) < 200
                and len(potential_title.split()) <= 10
                and not any(
                    x in potential_title.lower()
                    for x in ["follow", "message", "connect", "download", "email"]
                )
            ):
                return potential_title

    # Strategy 2: Look for elements with headline class
    for elem in soup.find_all(["div", "span"]):
        class_attr = elem.get("class", [])
        class_str = " ".join(class_attr) if class_attr else ""
        if "headline" in class_str.lower():
            title = _text(elem).strip()
            if title and len(title) < 200:
                return title

    # Strategy 3: Look for data-test attribute with headline
    for elem in soup.find_all(attrs={"data-test": True}):
        if "headline" in (elem.get("data-test") or "").lower():
            title = _text(elem).strip()
            if title and len(title) < 200:
                return title

    # Strategy 4: Look for common pattern "Title @Company" or "Title at Company"
    all_text = soup.get_text()
    match = re.search(
        r"([A-Za-z\s&]+?)\s*(?:@|at)\s*([A-Za-z0-9&\s\.\-,]+?)(?:\n|$|·|\|)", all_text
    )
    if match:
        title = match.group(1).strip()
        if (
            len(title) > 2
            and len(title) < 150
            and not any(x in title.lower() for x in ["message", "follow", "connect"])
        ):
            return title

    # Strategy 5: Look in experience section for first job title
    exp_section = soup.find(
        "section", {"class": lambda x: x and "experience" in (x or "").lower()}
    )
    if exp_section:
        first_item = exp_section.find("li")
        if first_item:
            item_text = _text(first_item)
            title_match = re.search(
                r"\b([A-Za-z ]+(?:Engineer|Developer|Manager|Analyst|Designer|Lead|Architect|Officer))\b",
                item_text,
            )
            if title_match:
                return title_match.group(1).strip()

    logger.debug("Could not extract job title from profile")
    return ""


def parse_location(soup: BeautifulSoup) -> str:
    """Extract location from profile - multiple strategies."""

    # Strategy 1: Look for location near header info
    header = soup.find("header")
    if header:
        for elem in header.find_all(["span", "div"]):
            text = _text(elem).strip()
            # Look for city/country pattern - usually after name/title
            if (
                "," in text
                and len(text) < 100
                and re.match(r"^[A-Za-z\s]+,\s*[A-Za-z\s,]+$", text)
            ):
                return text

    # Strategy 2: Look for location data attributes
    for elem in soup.find_all(attrs={"data-test": True}):
        if "location" in (elem.get("data-test") or "").lower():
            location = _text(elem).strip()
            if location and len(location) < 100:
                return location

    # Strategy 3: Look for span with location icon or class
    for elem in soup.find_all(["span", "div"]):
        class_attr = elem.get("class", [])
        class_str = " ".join(class_attr) if class_attr else ""
        if "location" in class_str.lower():
            location = _text(elem).strip()
            if location and len(location) < 100 and "," in location:
                return location

    # Strategy 4: Regex pattern on all text (City, Country or City, State, Country)
    all_text = soup.get_text()
    # Look for location pattern like "City, Country"
    match = re.search(r"([A-Za-z\s]+?),\s*([A-Za-z\s]+?)(?:\n|$|·|,)", all_text)
    if match:
        potential_location = f"{match.group(1)}, {match.group(2)}".strip()
        # Validate it's not header clutter
        if len(potential_location) < 100 and not any(
            x in potential_location.lower() for x in ["message", "connect", "follow"]
        ):
            return potential_location

    logger.debug("Could not extract location from profile")
    return ""


def parse_summary(soup: BeautifulSoup) -> str:
    """Extract about/summary section from LinkedIn profile - multiple strategies."""

    # Strategy 1: Look for inline-show-more-text elements (LinkedIn's summary container)
    for elem in soup.find_all(
        "div", {"class": lambda x: x and "inline-show-more-text" in (x or "")}
    ):
        # First try to get text from aria-hidden span (rendered text with line breaks preserved)
        hidden_span = elem.find("span", {"aria-hidden": "true"})
        if hidden_span:
            summary = _text(hidden_span).strip()
            if summary and len(summary) > 30:
                # Clean up the text - remove any HTML artifacts
                summary = re.sub(r"\s+", " ", summary)  # Normalize whitespace
                logger.debug(
                    f"Found summary via aria-hidden span: {len(summary)} chars"
                )
                return summary[:2000]

        # Fallback: get from visually-hidden span
        visible_span = elem.find(
            "span", {"class": lambda x: x and "visually-hidden" in (x or "")}
        )
        if visible_span:
            summary = _text(visible_span).strip()
            if summary and len(summary) > 30:
                summary = re.sub(r"\s+", " ", summary)
                logger.debug(
                    f"Found summary via visually-hidden span: {len(summary)} chars"
                )
                return summary[:2000]

    # Strategy 2: Look for specific summary section IDs/classes
    for selector in [
        "section[id*='about']",
        "div[class*='about']",
        "section[class*='summary']",
        "div[data-section='about']",
    ]:
        tag = soup.select_one(selector)
        if tag:
            summary = _text(tag).strip()
            if len(summary) > 50:
                summary = re.sub(r"\s+", " ", summary)
                logger.debug(
                    f"Found summary via selector '{selector}': {len(summary)} chars"
                )
                return summary[:2000]

    # Strategy 3: Look for substantial text in sections (excluding navigation)
    sections = soup.find_all("section")
    for section in sections:
        class_attr = section.get("class", [])
        class_str = " ".join(class_attr) if class_attr else ""
        # Skip known navigation/header sections
        if any(
            x in class_str.lower()
            for x in ["nav", "header", "footer", "profile-card", "title", "headline"]
        ):
            continue

        text = _text(section).strip()
        # Look for substantial text (likely about section) but not too long (avoid full page text)
        if 50 < len(text) < 5000:
            text = re.sub(r"\s+", " ", text)
            logger.debug(f"Found potential summary section: {len(text)} chars")
            return text[:2000]

    # Strategy 4: Look for paragraphs that might contain summary
    paragraphs = soup.find_all("p")
    for p in paragraphs:
        text = _text(p).strip()
        if len(text) > 100 and len(text) < 3000:
            # This is likely a substantial bio/summary paragraph
            text = re.sub(r"\s+", " ", text)
            logger.debug(f"Found summary in paragraph: {len(text)} chars")
            return text[:2000]

    logger.debug("Could not extract summary from profile")
    return ""


def extract_skills_from_text(text: str) -> list[str]:
    """Extract technical skills from text."""
    skills_keywords = [
        "Python",
        "JavaScript",
        "TypeScript",
        "Java",
        "C++",
        "C#",
        "Go",
        "Rust",
        "PHP",
        "Ruby",
        "Kotlin",
        "Swift",
        "React",
        "Vue",
        "Angular",
        "Next.js",
        "Svelte",
        "Node.js",
        "Express",
        "Django",
        "Flask",
        "FastAPI",
        "Spring",
        "MongoDB",
        "PostgreSQL",
        "MySQL",
        "Redis",
        "Firebase",
        "DynamoDB",
        "Elasticsearch",
        "AWS",
        "GCP",
        "Azure",
        "Docker",
        "Kubernetes",
        "Terraform",
        "Jenkins",
        "Git",
        "GitHub",
        "GitLab",
        "HTML",
        "CSS",
        "Tailwind",
        "Bootstrap",
        "GraphQL",
        "REST",
        "gRPC",
        "TensorFlow",
        "PyTorch",
        "Pandas",
        "NumPy",
        "Scikit-learn",
        "Machine Learning",
        "AI",
        "NLP",
        "Agile",
        "Scrum",
        "DevOps",
        "Microservices",
        "SQL",
        "NoSQL",
        "CI/CD",
    ]

    if not text:
        return []

    found_skills = set()
    text_lower = text.lower()

    for skill in skills_keywords:
        escaped_skill = skill.replace("+", "\\+").replace(".", "\\.")
        pattern = r"\b" + escaped_skill + r"\b"
        if re.search(pattern, text_lower, re.IGNORECASE):
            if skill == "C++":
                found_skills.add("C++")
            else:
                found_skills.add(skill)

    return sorted(found_skills)


def parse_experience(soup: BeautifulSoup) -> list[dict]:
    """Extract work experience - ONLY from actual list items with deduplication."""
    entries = []

    try:
        # Find all list items (these should be structured job entries)
        items = soup.find_all(
            "li", {"class": lambda x: x and "artdeco-list__item" in (x or "")}
        )

        if not items:
            logger.info("No experience list items found")
            return entries

        logger.info(f"Found {len(items)} total items to parse")

        # Helper to clean duplicated/corrupted text
        def clean_duplicates(text: str) -> str:
            """Remove immediately duplicated words from text."""
            if not text:
                return ""
            words = text.split()
            cleaned = []
            for i, word in enumerate(words):
                if i == 0 or word != words[i - 1]:
                    cleaned.append(word)
            return " ".join(cleaned)

        for item in items[:20]:  # Limit to prevent spam
            try:
                item_text = _text(item).strip()
                if len(item_text) < 10:
                    continue

                # Check if this looks like a job entry (has date and/or employment type)
                has_date = bool(
                    re.search(
                        r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|present)",
                        item_text,
                        re.IGNORECASE,
                    )
                )
                has_employment_type = bool(
                    re.search(
                        r"\b(Full-time|Part-time|Contract|Temporary|Freelance|Internship)\b",
                        item_text,
                    )
                )
                has_job_title = bool(
                    re.search(
                        r"\b(Engineer|Developer|Manager|Analyst|Designer|Lead|Senior|Junior|Architect|Specialist|Officer|Admin)\b",
                        item_text,
                    )
                )

                if not (has_job_title or (has_date and has_employment_type)):
                    continue

                # Extract fields carefully and clean duplicates
                job_role_match = re.search(
                    r"\b([A-Za-z ]+(?:Engineer|Developer|Manager|Analyst|Designer|Lead|Architect|Officer))\b",
                    item_text,
                )
                job_role = (
                    clean_duplicates(job_role_match.group(1).strip())
                    if job_role_match
                    else ""
                )

                company_match = re.search(
                    r"(?:at|@)\s+([A-Z][A-Za-z0-9&\s\-\.]+?)(?:\n|$|·|–|\|)", item_text
                )
                company_name = (
                    clean_duplicates(company_match.group(1).strip())
                    if company_match
                    else ""
                )

                emp_type_match = re.search(
                    r"\b(Full-time|Part-time|Contract|Internship|Temporary|Freelance)\b",
                    item_text,
                )
                job_type = emp_type_match.group(1) if emp_type_match else ""

                # Extract dates
                start_date = ""
                end_date = ""
                date_range = re.search(
                    r"([A-Za-z]+\s+\d{4})\s*(?:–|-|to)\s*(Present|[A-Za-z]+\s+\d{4})",
                    item_text,
                )
                if date_range:
                    start_date = date_range.group(1)
                    end_date = date_range.group(2)

                # Extract skills from job description
                skills = extract_skills_from_text(item_text)

                # Only add if we have meaningful data
                if job_role or company_name:
                    entry = {
                        "company_name": company_name or "Unknown",
                        "job_role": job_role or "Position",
                        "start_date": start_date,
                        "end_date": end_date,
                        "technology": skills,
                        "job_type": job_type,
                    }

                    # Deduplicate (check if same role at same company already exists)
                    is_duplicate = any(
                        clean_duplicates(e["job_role"])
                        == clean_duplicates(entry["job_role"])
                        and clean_duplicates(e["company_name"])
                        == clean_duplicates(entry["company_name"])
                        for e in entries
                    )
                    if not is_duplicate:
                        entries.append(entry)
                        logger.debug(f"Extracted exp: {job_role} at {company_name}")

            except Exception as e:
                logger.debug(f"Error parsing item: {str(e)}")
                continue

        logger.info(f"Experience: extracted {len(entries)} unique entries")

    except Exception as e:
        logger.error(f"Error parsing experience: {str(e)}")

    return entries


def parse_education(soup: BeautifulSoup) -> list[dict]:
    """Extract education - ONLY from actual list items."""
    entries = []

    try:
        items = soup.find_all(
            "li", {"class": lambda x: x and "artdeco-list__item" in (x or "")}
        )

        if not items:
            return entries

        for item in items[
            len(
                [
                    x
                    for x in items
                    if re.search(r"(Engineer|Developer|Manager|Lead)", _text(x))
                ]
            ) :
        ][:15]:  # Skip job items, limit education items
            try:
                item_text = _text(item).strip()
                if len(item_text) < 5:
                    continue

                # Check for degree keywords
                has_degree = bool(
                    re.search(
                        r"\b(Bachelor|Master|B\.S|B\.A|B\.Tech|M\.S|M\.A|M\.Tech|B\.E|M\.E|PhD|Diploma|Associate|Certificate|Degree)\b",
                        item_text,
                        re.IGNORECASE,
                    )
                )

                if not has_degree:
                    continue

                # Extract degree
                degree_match = re.search(
                    r"\b(Bachelor|Master|M\.Tech|B\.Tech|B\.E|M\.E|B\.S|M\.S|Ph?D|Diploma)\b",
                    item_text,
                    re.IGNORECASE,
                )
                degree_type = degree_match.group(1) if degree_match else "Degree"

                # Extract course/field
                course_match = re.search(
                    r"(?:in|of)\s+([A-Za-z\s&\-\.]+?)(?:\s+from|\s+at|$|\n|·)",
                    item_text,
                    re.IGNORECASE,
                )
                course_name = (
                    course_match.group(1).strip() if course_match else "Not specified"
                )

                # Extract school
                school_match = re.search(
                    r"(?:from|at)\s+([A-Z][A-Za-z0-9&\s\.\-,]+?)(?:$|\n|·|,)", item_text
                )
                school_name = school_match.group(1).strip() if school_match else ""

                # Extract year
                year_match = re.search(r"\b(?:20|19)\d{2}\b", item_text)
                graduation_year = year_match.group(0) if year_match else ""

                if degree_type or school_name or course_name:
                    entry = {
                        "degree": degree_type,
                        "course": course_name,
                        "school_name": school_name,
                        "graduation_year": graduation_year,
                    }

                    # Deduplicate
                    is_duplicate = any(
                        e["degree"] == entry["degree"]
                        and e["course"] == entry["course"]
                        for e in entries
                    )
                    if not is_duplicate:
                        entries.append(entry)
                        logger.debug(f"Extracted edu: {degree_type} in {course_name}")

            except Exception as e:
                logger.debug(f"Error parsing education: {str(e)}")
                continue

        logger.info(f"Education: extracted {len(entries)} entries")

    except Exception as e:
        logger.error(f"Error parsing education: {str(e)}")

    return entries


def parse_certifications(soup: BeautifulSoup) -> list[dict]:
    """Extract certifications."""
    certs = []

    try:
        all_text = soup.get_text()

        # Look for certification patterns
        cert_patterns = [
            r"(AWS Certified [A-Za-z\s]+)",
            r"(Google Cloud Certified [A-Za-z\s]+)",
            r"(Azure Certified [A-Za-z\s]+)",
            r"(Certified [A-Za-z\s]+)",
        ]

        for pattern in cert_patterns:
            matches = re.finditer(pattern, all_text, re.IGNORECASE)
            for match in matches:
                cert_name = match.group(1).strip()
                if len(cert_name) > 5:
                    techs = extract_skills_from_text(cert_name)
                    certs.append(
                        {
                            "certification_name": cert_name,
                            "issuer": "",
                            "related_technology": techs,
                        }
                    )

        # Deduplicate
        unique_certs = []
        seen = set()
        for cert in certs:
            if cert["certification_name"] not in seen:
                seen.add(cert["certification_name"])
                unique_certs.append(cert)

        logger.info(f"Certifications: extracted {len(unique_certs)} entries")
        return unique_certs[:5]

    except Exception as e:
        logger.error(f"Error parsing certifications: {str(e)}")
        return certs


def parse_projects(soup: BeautifulSoup) -> list[dict]:
    """Extract projects - ONLY from actual list items with duration extraction."""
    projects = []

    try:
        items = soup.find_all(
            "li", {"class": lambda x: x and "artdeco-list__item" in (x or "")}
        )

        if not items:
            return projects

        # Helper to extract duration patterns
        def extract_duration(text: str) -> str:
            """Extract duration from text like '4 yrs 2 mos' or 'Feb 2023 - Present'."""
            if not text:
                return ""

            # Pattern: "X yrs Y mos"
            match = re.search(r"(\d+)\s*yrs?\s+(\d+)\s*mos?", text, re.IGNORECASE)
            if match:
                return f"{match.group(1)} years {match.group(2)} months"

            # Pattern: "X years" standalone
            match = re.search(r"(\d+)\s*yrs?(?:\s|$|·)", text, re.IGNORECASE)
            if match:
                return f"{match.group(1)} years"

            # Pattern: "X months"
            match = re.search(r"(\d+)\s*mos?(?:\s|$|·)", text, re.IGNORECASE)
            if match:
                return f"{match.group(1)} months"

            return ""

        # Get only items that look like projects (not jobs/education)
        for item in items:
            try:
                item_text = _text(item).strip()

                if len(item_text) < 15:
                    continue

                # Check for project keywords
                has_project_keyword = bool(
                    re.search(
                        r"\b(developed|built|created|implemented|designed|project|portfolio|application|tool|system)\b",
                        item_text,
                        re.IGNORECASE,
                    )
                )

                # Make sure it doesn't look like a job entry (don't include pure job roles)
                is_job_only = bool(
                    re.search(
                        r"(Full-time|Part-time|Contract).*?(?:Engineer|Developer|Manager|Lead)",
                        item_text,
                        re.IGNORECASE,
                    )
                )

                if not has_project_keyword and not is_job_only:
                    continue

                # Extract title (first line, max 100 chars)
                title_candidate = item_text.split("\n")[0][:150].strip()

                # Clean title by removing duplicated consecutive words
                title_words = title_candidate.split()
                title_cleaned = []
                for i, word in enumerate(title_words):
                    if i == 0 or word != title_words[i - 1]:
                        title_cleaned.append(word)
                title = " ".join(title_cleaned)

                if not title or len(title) < 3:
                    continue

                # Extract description (up to 300 chars to preserve context for LLM extraction)
                description = item_text[:300]

                # Extract duration (CRITICAL - try multiple strategies)
                duration = extract_duration(item_text)

                # Extract technologies
                techs = extract_skills_from_text(item_text)

                projects.append(
                    {
                        "title": title,
                        "description": description,
                        "technology_used": techs,
                        "duration": duration,
                    }
                )
                logger.debug(f"Extracted project: {title} (duration: {duration})")

            except Exception as e:
                logger.debug(f"Error parsing project: {str(e)}")
                continue

        logger.info(f"Projects: extracted {len(projects)} entries with durations")

    except Exception as e:
        logger.error(f"Error parsing projects: {str(e)}")

    return projects


def parse_skills(soup: BeautifulSoup) -> list[str]:
    """Extract skills from profile."""
    # Combine title, summary, and experience text
    title = parse_title(soup)
    summary = parse_summary(soup)
    all_text = soup.get_text()

    combined_text = f"{title} {summary} {all_text}".lower()
    skills = extract_skills_from_text(combined_text)

    logger.info(f"Skills: extracted {len(skills)} skills")
    return skills[:20]  # Limit to top 20


def parse_contact(soup: BeautifulSoup) -> tuple[str, str]:
    """Extract email and phone."""
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
    """Parse LinkedIn profile into structured candidate data."""
    soup = BeautifulSoup(html, "lxml")

    email, phone = parse_contact(soup)
    skills = parse_skills(soup)
    experience = parse_experience(soup)
    education = parse_education(soup)
    certifications = parse_certifications(soup)
    projects = parse_projects(soup)
    name = parse_name(soup)
    title = parse_title(soup)
    location = parse_location(soup)
    summary = parse_summary(soup)

    # Save HTML for debugging
    try:
        import hashlib

        url_hash = hashlib.md5(profile_url.encode()).hexdigest()
        with open(f"/tmp/linkedin_profile_{url_hash}.html", "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"Saved HTML for analysis: {url_hash}")
    except Exception as e:
        logger.debug(f"Could not save HTML: {e}")

    logger.info(
        "profile_parsed",
        name=name,
        title=title,
        experience_count=len(experience),
        education_count=len(education),
        certifications_count=len(certifications),
        projects_count=len(projects),
        skills_count=len(skills),
        url=profile_url,
    )

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "location": location,
        "title": title,
        "summary": summary,
        "hard_skills": skills,
        "soft_skills": [],
        "experience": experience,
        "education": education,
        "certifications": certifications,
        "projects": projects,
        "profile_url": profile_url,
    }

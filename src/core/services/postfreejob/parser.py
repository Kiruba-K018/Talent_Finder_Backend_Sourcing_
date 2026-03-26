"""Parser for PostJobFree resume text."""

import re
from datetime import datetime

from src.observability.logging.logger import get_logger

logger = get_logger(__name__)


def parse_postjobfree_resume(raw_text: str) -> dict:
    """
    Parse raw PostJobFree resume text into structured format.

    Args:
        raw_text: Raw text extracted from PostJobFree resume page

    Returns:
        Parsed candidate dict with structured data
    """
    try:
        if not raw_text or not isinstance(raw_text, str):
            logger.warning(
                "empty_or_invalid_resume_text", text_type=type(raw_text).__name__
            )
            return {}

        if not raw_text.strip():
            logger.warning("empty_resume_text")
            return {}

        candidate = {
            "raw_text": raw_text,
            "candidate_name": _extract_name(raw_text),
            "title": _extract_title(raw_text),
            "summary": _extract_summary(raw_text),
            "location": _extract_location(raw_text),
            "contact_phone": _extract_phone(raw_text),
            "candidate_email": _extract_email(raw_text),
            "contact_linkedin_url": _extract_linkedin_url(raw_text),
            "portfolio_url": _extract_portfolio_url(raw_text),
            "hard_skills": _extract_hard_skills(raw_text),
            "soft_skills": _extract_soft_skills(raw_text),
            "experience": _extract_experience(raw_text),
            "projects": _extract_projects(raw_text),
            "education": _extract_education(raw_text),
        }

        logger.info("resume_parsed", name=candidate.get("candidate_name"))
        return candidate
    except Exception as e:
        logger.error(
            "parse_postjobfree_resume_failed",
            error=str(e),
            exception_type=type(e).__name__,
        )
        return {}


def _extract_name(text: str) -> str | None:
    """Extract candidate name from resume text.

    First checks for structured CANDIDATE_NAME: prefix added by scraper.
    Falls back to heuristic extraction from first lines if not found.
    Filters out common false positives like locations and company names.
    """
    try:
        if not text or not isinstance(text, str):
            return None

        # Check for structured format from scraper: "CANDIDATE_NAME: ..."
        candidate_name_match = re.search(
            r"^CANDIDATE_NAME:\s*(.+)$", text, re.MULTILINE
        )
        if candidate_name_match:
            name = candidate_name_match.group(1).strip()
            # Validate the extracted name
            if name and len(name) > 2 and re.search(r"[a-zA-Z]", name):
                # Remove honorifics if present
                name = re.sub(
                    r"\b(Jr|Sr|Mr|Ms|Mrs|Dr|Prof|MD|PhD)\b\.?",
                    "",
                    name,
                    flags=re.IGNORECASE,
                ).strip()
                if name and len(name) > 2:
                    logger.debug("extracted_name_from_structured_format", name=name)
                    return name

        # Fallback: Extract from first few lines if structured format not found
        lines = [line.strip() for line in text.split("\n") if line and line.strip()]

        if not lines:
            return None

        # List of words that indicate location or non-name lines
        location_keywords = [
            "experience",
            "education",
            "skill",
            "project",
            "about",
            "summary",
            "india",
            "delhi",
            "chennai",
            "bangalore",
            "mumbai",
            "pune",
            "hyderabad",
            "california",
            "new york",
            "texas",
            "florida",
            "usa",
            "uk",
            "canada",
            "australia",
            "uae",
            "singapore",
            "london",
            "dubai",
            "sydney",
            "tamil nadu",
            "maharashtra",
            "karnataka",
            "telangana",
            "pvt",
            "ltd",
            "inc",
            "llc",
            "corporation",
            "company",
            "co.",
            "at ",
            "street",
            "avenue",
            "road",
            "lane",
            "drive",
            "boulevard",
        ]

        # First few non-empty lines likely contain the name
        for line in lines[:5]:
            line_lower = line.lower()

            # Skip CANDIDATE_NAME marker line if it exists
            if line_lower.startswith("candidate_name:"):
                continue

            # Skip lines that look like locations or section headers
            if any(keyword in line_lower for keyword in location_keywords):
                continue

            # Skip lines with state/country pattern (e.g., "City, State, Country")
            if line.count(",") >= 2 and ("india" in line_lower or "usa" in line_lower):
                continue

            # Skip lines with too many words (probably not a name)
            words = line.split()
            if len(words) > 5:
                continue

            # Skip very long lines
            if len(line) >= 50:
                continue

            # Remove honorifics and extract candidate name
            name = re.sub(
                r"\b(Jr|Sr|Mr|Ms|Mrs|Dr|Prof|MD|PhD)\b\.?",
                "",
                line,
                flags=re.IGNORECASE,
            ).strip()

            # Validate name format (should have letters, preferably 1-2 words)
            if (
                name
                and len(name) > 2
                and re.search(r"[a-zA-Z]", name)
                and (
                    ", " not in name
                    or not any(loc in name.lower() for loc in location_keywords)
                )
            ):
                logger.debug("extracted_name_from_fallback_heuristic", name=name)
                return name

        return None
    except Exception as e:
        logger.debug("extract_name_error", error=str(e))
        return None


def _extract_title(text: str) -> str | None:
    """Extract current job title."""
    try:
        if not text or not isinstance(text, str):
            return None

        # Look for job title patterns
        patterns = [
            r"(?:Current\s+)?(?:Title|Position|Role)[:\s]+([^\n]+)",
            r"([A-Z][a-zA-Z\s]{3,})(?:\s+(?:at|@|\|))",  # Title at Company
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                if len(title) < 100:  # Sanity check
                    return title

        # Look in first few lines for job titles
        lines = [
            line.strip() for line in text.split("\n")[:10] if line and line.strip()
        ]
        for line in lines:
            if any(
                keyword in line.lower()
                for keyword in [
                    "developer",
                    "engineer",
                    "manager",
                    "analyst",
                    "architect",
                    "specialist",
                ]
            ):
                # Clean up the line
                title = re.sub(r"[0-9+\*]+", "", line).strip()
                if 3 < len(title) < 100:
                    return title

        return None
    except Exception as e:
        logger.debug("extract_title_error", error=str(e))
        return None


def _extract_summary(text: str) -> str | None:
    """Extract professional summary."""
    try:
        if not text or not isinstance(text, str):
            return None

        # Look for ABOUT ME or SUMMARY section
        about_match = re.search(
            r"(?:ABOUT ME|SUMMARY|PROFESSIONAL SUMMARY)[:\n]+([^\n]*(?:\n(?![A-Z\s]*[A-Z][:\n])[^\n]*)*)",
            text,
            re.IGNORECASE,
        )

        if about_match:
            summary = about_match.group(1).strip()
            # Take first sentence or first 300 chars
            sentences = summary.split(".")
            if sentences:
                return (
                    (sentences[0] + ".").strip()
                    if not sentences[0].endswith(".")
                    else sentences[0].strip()
                )

        return None
    except Exception as e:
        logger.debug("extract_summary_error", error=str(e))
        return None


def _extract_location(text: str) -> str | None:
    """Extract location/city information."""
    try:
        if not text or not isinstance(text, str):
            return None

        # Look for city, country pattern
        location_pattern = (
            r"([A-Za-z\s]+),\s*([A-Za-z\s]+),\s*(India|USA|UK|UAE|Canada|Australia)"
        )
        match = re.search(location_pattern, text)
        if match:
            return f"{match.group(1)}, {match.group(3)}".strip()

        # Look for simpler pattern
        lines = text.split("\n")
        for line in lines:
            if line and (
                "india" in line.lower()
                or "delhi" in line.lower()
                or "bangalore" in line.lower()
            ):
                # Extract location from line
                location = re.search(
                    r"([A-Za-z\s]+)\s*,\s*(India|Delhi|Bangalore|Mumbai|Chennai)",
                    line,
                    re.IGNORECASE,
                )
                if location:
                    return location.group(0).strip()

        return None
    except Exception as e:
        logger.debug("extract_location_error", error=str(e))
        return None


def _extract_phone(text: str) -> str | None:
    """Extract phone number."""
    try:
        if not text or not isinstance(text, str):
            return None

        # Look for Indian phone pattern or masked pattern
        patterns = [
            r"\+91[-\s]?[0-9\*]{10}",  # +91-9999999999 or +91-999*****
            r"[0-9]{10}",  # 10 digit phone
            r"\+[0-9]+-[0-9\*]+",  # International format with mask
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()

        return None
    except Exception as e:
        logger.debug("extract_phone_error", error=str(e))
        return None


def _extract_email(text: str) -> str | None:
    """Extract email address."""
    try:
        if not text or not isinstance(text, str):
            return None

        # Look for regular email or masked pattern
        patterns = [
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # Regular email
            r"[a-zA-Z0-9._%\*-]+@[a-zA-Z0-9.\*-]+\.[a-zA-Z]{2,}",  # Masked email
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                email = match.group(0).strip()
                if (
                    email.count("@") == 1 and "*" not in email or "*" not in email
                ):  # Prefer unmasked
                    return email

        return None
    except Exception as e:
        logger.debug("extract_email_error", error=str(e))
        return None


def _extract_linkedin_url(text: str) -> str | None:
    """Extract LinkedIn profile URL."""
    try:
        if not text or not isinstance(text, str):
            return None

        match = re.search(r"https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-]+/?", text)
        if match:
            return match.group(0).strip()
        return None
    except Exception as e:
        logger.debug("extract_linkedin_url_error", error=str(e))
        return None


def _extract_portfolio_url(text: str) -> str | None:
    """Extract GitHub or portfolio URL."""
    try:
        if not text or not isinstance(text, str):
            return None

        patterns = [
            r"https?://(?:www\.)?github\.com/[a-zA-Z0-9\-]+/?",
            r"https?://(?:www\.)?portfolio\.[a-zA-Z0-9\-\.]+",
            r"https?://[a-zA-Z0-9\-\.]+\.com",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                url = match.group(0).strip()
                if "linkedin" not in url.lower():  # Exclude LinkedIn
                    return url

        return None
    except Exception as e:
        logger.debug("extract_portfolio_url_error", error=str(e))
        return None


def _extract_hard_skills(text: str) -> list[str]:
    """Extract technical skills."""
    try:
        if not text or not isinstance(text, str):
            return []

        # Common hard skills to look for
        tech_keywords = [
            "Python",
            "Java",
            "JavaScript",
            "C++",
            "C#",
            "PHP",
            "Ruby",
            "Go",
            "Rust",
            "Kotlin",
            "FastAPI",
            "Django",
            "Flask",
            "Spring Boot",
            "NestJS",
            "Laravel",
            "React",
            "Vue",
            "Angular",
            "Node.js",
            "Express",
            "TypeScript",
            "SQL",
            "PostgreSQL",
            "MySQL",
            "MongoDB",
            "Redis",
            "Docker",
            "Kubernetes",
            "AWS",
            "GCP",
            "Azure",
            "Git",
            "Jenkins",
            "CI/CD",
            "REST API",
            "GraphQL",
            "Microservices",
            "Linux",
            "Windows",
            "Terraform",
            "Prometheus",
            "Grafana",
            "Kafka",
            "Airflow",
            "Spark",
            "Hadoop",
            "TensorFlow",
            "PyTorch",
            "Scikit-learn",
            "NumPy",
            "Pandas",
            "AI",
            "Machine Learning",
            "Deep Learning",
            "NLP",
            "Computer Vision",
            "Ansible",
            "Helm",
            "Nginx",
            "Apache",
            "Shopify",
            "WordPress",
            "Bootstrap",
            "Tailwind",
            "HTML",
            "CSS",
            "XML",
            "JSON",
            "Power BI",
            "Jupyter",
            "PyCharm",
            "VS Code",
            "Postman",
            "MVC",
            "MVVM",
            "API Integration",
            "Payment Gateway",
            "Third-party API",
        ]

        skills = []
        text_lower = text.lower()

        for skill in tech_keywords:
            if skill.lower() in text_lower and skill not in skills:
                skills.append(skill)

        return skills[:20]  # Limit to top 20
    except Exception as e:
        logger.debug("extract_hard_skills_error", error=str(e))
        return []


def _extract_soft_skills(text: str) -> list[str]:
    """Extract soft skills."""
    try:
        if not text or not isinstance(text, str):
            return []

        soft_keywords = [
            "Communication",
            "Leadership",
            "Team Collaboration",
            "Problem Solving",
            "Agile",
            "Scrum",
            "Project Management",
            "Time Management",
            "Critical Thinking",
            "Mentorship",
            "Negotiation",
            "Presentation",
            "Attention to Detail",
            "Adaptability",
            "Accountability",
            "Initiative",
            "Teamwork",
            "Creativity",
            "Decision Making",
            "Work Ethic",
        ]

        skills = []
        text_lower = text.lower()

        for skill in soft_keywords:
            if skill.lower() in text_lower and skill not in skills:
                skills.append(skill)

        return skills
    except Exception as e:
        logger.debug("extract_soft_skills_error", error=str(e))
        return []


def _extract_experience(text: str) -> list[dict]:
    """Extract work experience entries."""
    try:
        if not text or not isinstance(text, str):
            return []

        experience = []

        # Look for PROFESSIONAL EXPERIENCE or EXPERIENCE section
        exp_section = re.search(
            r"PROFESSIONAL\s+EXPERIENCE(?:\n|[^\n]*\n)(.*?)(?=\nEDUCATION|\nKEY\s+PROJECTS|\nTOOLS|\nLANGUAGES|\nCERTIFICATIONS|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )

        if not exp_section:
            return experience

        exp_text = exp_section.group(1)
        if not exp_text or not isinstance(exp_text, str):
            return experience

        # Split by company/role patterns
        # This is a simplified extraction - real resumes may need more sophisticated parsing
        lines = exp_text.split("\n")
        current_exp = {}

        for line in lines:
            line = line.strip()
            if not line:
                if current_exp and "company_name" in current_exp:
                    experience.append(current_exp)
                    current_exp = {}
                continue

            # Look for company names (often in CAPS or followed by "Ltd", "Inc", etc.)
            if any(
                keyword in line
                for keyword in ["Ltd", "Inc", "Pvt", "LLC", "Corporation", "Co."]
            ) or (len(line) < 50 and line.isupper()):
                if current_exp and "company_name" in current_exp:
                    experience.append(current_exp)
                current_exp = {"company_name": line}

            # Look for dates
            date_pattern = r"([A-Za-z]+,?\s*\d{4})\s*-\s*(?:(Present|Current)|([A-Za-z]+,?\s*\d{4}))"
            date_match = re.search(date_pattern, line)
            if date_match and "company_name" in current_exp:
                current_exp["start_date"] = _parse_date_string(date_match.group(1))
                if date_match.group(2):  # Present/Current
                    current_exp["end_date"] = None
                else:
                    current_exp["end_date"] = _parse_date_string(date_match.group(3))

            # Look for job role/title
            if (
                any(
                    keyword in line
                    for keyword in [
                        "Developer",
                        "Engineer",
                        "Manager",
                        "Analyst",
                        "Lead",
                        "Senior",
                        "Junior",
                    ]
                )
                and "company_name" in current_exp
                and "job_role" not in current_exp
            ):
                current_exp["job_role"] = line

        if current_exp and "company_name" in current_exp:
            experience.append(current_exp)

        return experience
    except Exception as e:
        logger.debug("extract_experience_error", error=str(e))
        return []


def _extract_projects(text: str) -> list[dict]:
    """Extract project details."""
    try:
        if not text or not isinstance(text, str):
            return []

        projects = []

        # Look for KEY PROJECTS or PROJECTS section
        proj_section = re.search(
            r"KEY\s+PROJECTS(?:\n|[^\n]*\n)(.*?)(?=\nTOOLS|\nEDUCATION|\nLANGUAGES|\nCERTIFICATIONS|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )

        if not proj_section:
            return projects

        proj_text = proj_section.group(1)
        if not proj_text or not isinstance(proj_text, str):
            return projects

        # Split projects by delimiter patterns
        project_blocks = re.split(r"\n(?=[A-Z][a-zA-Z\s]+\s*(?:–|—|-))", proj_text)

        for block in project_blocks:
            lines = [line.strip() for line in block.split("\n") if line.strip()]
            if not lines:
                continue

            project = {
                "title": lines[0] if lines else "",
                "description": "\n".join(lines[1:]) if len(lines) > 1 else "",
                "technology_used": [],
                "duration": None,
            }

            # Extract technology stack from description
            tech_keywords = [
                "Python",
                "Java",
                "JavaScript",
                "React",
                "Django",
                "FastAPI",
                "PostgreSQL",
                "AWS",
                "Docker",
            ]
            for tech in tech_keywords:
                if tech.lower() in project["description"].lower():
                    project["technology_used"].append(tech)

            if project["title"]:
                projects.append(project)

        return projects
    except Exception as e:
        logger.debug("extract_projects_error", error=str(e))
        return []


def _extract_education(text: str) -> list[dict]:
    """Extract education details."""
    try:
        if not text or not isinstance(text, str):
            return []

        education = []

        # Look for EDUCATION section
        edu_section = re.search(
            r"EDUCATION(?:\n|[^\n]*\n)(.*?)(?=\nCERTIFICATIONS|\nEXPERIENCE|\nLANGUAGES|\nTOOLS|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )

        if not edu_section:
            return education

        edu_text = edu_section.group(1)
        if not edu_text or not isinstance(edu_text, str):
            return education

        # Look for degree patterns
        degree_patterns = [
            r"(?:Master of Science|M\.Sc|MSc|M\.Tech)[^\n]*([A-Za-z\s&-]+)",
            r"(?:Bachelor of Technology|B\.Tech|Bachelor of Science|B\.Sc|B\.E)[^\n]*([A-Za-z\s&-]+)",
            r"(?:Master of Business Administration|MBA)[^\n]*([A-Za-z\s&-]+)?",
            r"(?:Diploma)[^\n]*([A-Za-z\s&-]+)?",
        ]

        for degree_pattern in degree_patterns:
            matches = re.finditer(degree_pattern, edu_text, re.IGNORECASE)
            for match in matches:
                degree_match = re.search(
                    r"(M\.Sc|MSc|M\.Tech|B\.Tech|B\.Sc|MBA|Diploma|Bachelor|Master)",
                    match.group(0),
                    re.IGNORECASE,
                )
                course_match = (
                    match.group(1) if match.lastindex and match.lastindex >= 1 else ""
                )

                if degree_match:
                    education.append(
                        {
                            "degree": degree_match.group(0).strip(),
                            "course": course_match.strip() if course_match else "",
                        }
                    )

        return education
    except Exception as e:
        logger.debug("extract_education_error", error=str(e))
        return []


def _parse_date_string(date_str: str) -> str | None:
    """Parse date string to YYYY-MM-DD format.

    Args:
        date_str: Date string in various formats

    Returns:
        Date in YYYY-MM-DD format or None if parsing fails
    """
    try:
        if not date_str or not isinstance(date_str, str):
            return None

        date_str = date_str.strip()
        if not date_str:
            return None

        # Try various date formats
        formats = [
            "%B, %Y",  # January, 2023
            "%b, %Y",  # Jan, 2023
            "%B %Y",  # January 2023
            "%b %Y",  # Jan 2023
            "%m/%d/%Y",  # 01/15/2023
            "%Y-%m-%d",  # 2023-01-15
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        # If parsing fails, return None
        return None
    except Exception as e:
        logger.debug("parse_date_string_error", error=str(e), date_str=date_str)
        return None

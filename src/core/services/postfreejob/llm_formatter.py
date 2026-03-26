"""LLM-based formatter for PostJobFree resume data."""

import json
import re

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from src.config.settings import get_settings
from src.observability.logging.logger import get_logger

logger = get_logger(__name__)


def format_postjobfree_resume_from_html(html_content: str) -> dict:
    """
    Format PostJobFree resume data directly from HTML content.

    Uses the PostJobFree HTML structure template:
    - 1st <p> tag: candidate name
    - 2nd <p> tag: title
    - 3rd-4th <p> tags: summary
    - Middle <p> tags: experience and projects
    - Last <p> tag: education, LinkedIn, GitHub

    Args:
        html_content: Raw HTML from PostJobFree resume page

    Returns:
        Formatted candidate dict matching MongoDB schema
    """
    try:
        # Extract all <p> tags from div.normalText
        div_match = re.search(
            r'<div[^>]*class=["\']normalText["\'][^>]*>(.*?)</div>',
            html_content,
            re.DOTALL | re.IGNORECASE,
        )
        if not div_match:
            logger.warning("normalText_div_not_found_in_html")
            return _get_empty_candidate()

        div_content = div_match.group(1)

        # Extract all <p> tags
        p_tags = re.findall(r"<p[^>]*>(.*?)</p>", div_content, re.DOTALL)

        if not p_tags:
            logger.warning("no_p_tags_found_in_normalText_div")
            return _get_empty_candidate()

        # Clean HTML tags and get text content
        cleaned_p_texts = []
        for p_tag in p_tags:
            # Remove HTML tags
            text = re.sub(r"<[^>]+>", "", p_tag)
            # Decode HTML entities
            text = (
                text.replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&quot;", '"')
                .replace("&#039;", "'")
            )
            text = text.strip()
            if text:  # Only keep non-empty paragraphs
                cleaned_p_texts.append(text)

        if not cleaned_p_texts:
            logger.warning("all_p_tags_empty_after_cleaning")
            return _get_empty_candidate()

        logger.info(
            "extracted_p_tags_from_html",
            total_p_tags=len(cleaned_p_texts),
            first_three=[
                cleaned_p_texts[i] if i < len(cleaned_p_texts) else None
                for i in range(3)
            ],
        )

        # Map p tags to resume sections
        structured_data = {
            "p_tags": cleaned_p_texts,
            "candidate_name": cleaned_p_texts[0] if len(cleaned_p_texts) > 0 else None,
            "title": cleaned_p_texts[1] if len(cleaned_p_texts) > 1 else None,
            "summary_start": cleaned_p_texts[2] if len(cleaned_p_texts) > 2 else None,
            "middle_content": cleaned_p_texts[3:-1] if len(cleaned_p_texts) > 4 else [],
            "last_p_tag": cleaned_p_texts[-1] if len(cleaned_p_texts) > 0 else None,
        }

        logger.debug(
            "structured_html_resume_data",
            data=json.dumps(structured_data, default=str)[:500],
        )

        # Send to LLM for intelligent extraction
        return _format_with_llm_from_html_structure(structured_data, html_content)

    except Exception as e:
        logger.error("failed_to_parse_html_resume", error=str(e))
        return _get_empty_candidate()


def _format_with_llm_from_html_structure(
    structured_data: dict, original_html: str
) -> dict:
    """
    Use LLM to intelligently parse structured HTML resume data.

    Args:
        structured_data: Pre-extracted data from HTML p tags
        original_html: Original HTML for context

    Returns:
        Formatted candidate dict
    """
    try:
        settings = get_settings()

        if not settings.groq_api_key:
            logger.warning(
                "groq_api_key_not_configured, using extracted HTML data as-is"
            )
            return _parse_html_structure_without_llm(structured_data)

        # Initialize LLM
        try:
            # Initialize LLM
            llm = init_chat_model(
                model="openai/gpt-oss-120b",
                model_provider="groq",
                temperature=0,
                max_tokens=4000,
                api_key=settings.groq_api_key_tertiary,
            )
        except Exception as e_p:
            logger.error("failed_to_initialize_llm_with_primary_key", error=str(e_p))
            try:
                llm = init_chat_model(
                    model="openai/gpt-oss-120b",
                    model_provider="groq",
                    temperature=0,
                    max_tokens=4000,
                    api_key=settings.groq_api_key_secondary,
                )
            except Exception as e_s:
                logger.error(
                    "failed_to_initialize_llm_with_secondary_key", error=str(e_s)
                )
                llm = init_chat_model(
                    model="openai/gpt-oss-120b",
                    model_provider="groq",
                    temperature=0,
                    max_tokens=4000,
                    api_key=settings.groq_api_key,
                )

        # Create system prompt for HTML-based extraction
        system_prompt = SystemMessage(
            content="""You are an expert resume parser specializing in PostJobFree HTML structure.

POSTJOBFREE HTML STRUCTURE:
- <p> Index 0: Candidate Name
- <p> Index 1: Current Job Title  
- <p> Index 2-4: Professional Summary/About section
- <p> Index 5 onwards: Experience, Projects, Technical Skills
- Last <p>: Education, LinkedIn, GitHub links

EXTRACTION RULES:
1. Extract ONLY information that is clearly present
2. Return NULL for missing fields, not assumptions
3. Parse dates as YYYY-MM-DD or null
4. Distinguish technical (hard_skills) vs behavioral (soft_skills)
5. Extract URLs and links accurately
6. For masked emails/phones, include the masked format

Return ONLY valid JSON."""
        )

        # Create detailed user prompt
        user_prompt = HumanMessage(
            content=f"""Parse this PostJobFree resume HTML structure and extract all candidate information:

Extracted P Tags:
{json.dumps(structured_data, indent=2, default=str)}

Please extract and structure the complete resume data including:
- Candidate name, title, summary
- All technical and soft skills
- Complete work experience with dates and companies
- All projects with descriptions and tech stack
- Education and certifications
- Contact information (email, phone, LinkedIn, GitHub)
- Location

Return as JSON with complete structure matching all fields."""
        )

        logger.debug("calling_llm_for_html_parsing")
        response = llm.invoke([system_prompt, user_prompt])
        response_text = response.content.strip()

        # Extract JSON from response
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if not json_match:
            logger.warning(
                "llm_html_parsing_invalid_json", response=response_text[:200]
            )
            return _parse_html_structure_without_llm(structured_data)

        formatted = json.loads(json_match.group(0))
        logger.info(
            "html_resume_formatted_with_llm",
            candidate_name=formatted.get("candidate_name"),
        )

        return _prepare_candidate_data(formatted)

    except Exception as e:
        logger.error("failed_to_format_html_with_llm", error=str(e))
        return _parse_html_structure_without_llm(structured_data)


def _parse_html_structure_without_llm(structured_data: dict) -> dict:
    """
    Parse HTML structure without LLM (fallback).
    Uses heuristic rules to extract data from p tag positions.
    """
    try:
        p_tags = structured_data.get("p_tags", [])

        candidate_data = {
            "candidate_name": _extract_text(p_tags[0]) if len(p_tags) > 0 else None,
            "title": _extract_text(p_tags[1]) if len(p_tags) > 1 else None,
            "summary": _extract_text(p_tags[2]) if len(p_tags) > 2 else None,
            "hard_skills": _extract_skills_from_text(" ".join(p_tags)),
            "soft_skills": _extract_soft_skills_from_text(" ".join(p_tags)),
            "location": _extract_location_from_text(" ".join(p_tags)),
            "contact_phone": _extract_phone_from_text(" ".join(p_tags)),
            "candidate_email": _extract_email_from_text(" ".join(p_tags)),
            "contact_linkedin_url": _extract_linkedin_from_text(" ".join(p_tags)),
            "portfolio_url": None,
            "experience": [],
            "projects": [],
            "education": [],
        }

        logger.debug(
            "parsed_html_structure_without_llm",
            candidate_name=candidate_data.get("candidate_name"),
        )
        return _prepare_candidate_data(candidate_data)

    except Exception as e:
        logger.error("failed_to_parse_html_structure", error=str(e))
        return _get_empty_candidate()


def _extract_text(text: str) -> str | None:
    """Extract and clean text."""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    return text if text else None


def _extract_skills_from_text(text: str) -> list[str]:
    """Extract technical skills from text."""
    skills = []
    tech_keywords = [
        "Python",
        "Java",
        "JavaScript",
        "C++",
        "PHP",
        "FastAPI",
        "Django",
        "Laravel",
        "React",
        "Vue",
        "Angular",
        "Node.js",
        "PostgreSQL",
        "MySQL",
        "MongoDB",
        "Docker",
        "Kubernetes",
        "AWS",
        "Azure",
        "GCP",
        "Git",
        "REST API",
        "GraphQL",
        "Shopify",
        "WordPress",
        "NumPy",
        "Pandas",
        "Power BI",
    ]
    for skill in tech_keywords:
        if skill.lower() in text.lower() and skill not in skills:
            skills.append(skill)
    return skills[:20]


def _extract_soft_skills_from_text(text: str) -> list[str]:
    """Extract soft skills from text."""
    skills = []
    soft_keywords = [
        "Communication",
        "Leadership",
        "Team Collaboration",
        "Problem Solving",
        "Agile",
        "Scrum",
        "Project Management",
        "Mentorship",
    ]
    for skill in soft_keywords:
        if skill.lower() in text.lower() and skill not in skills:
            skills.append(skill)
    return skills


def _extract_location_from_text(text: str) -> str | None:
    """Extract location from text."""
    location_pattern = (
        r"\b(Noida|Delhi|Bangalore|Mumbai|Pune|Hyderabad|Chennai|India|UAE|Dubai)\b"
    )
    match = re.search(location_pattern, text, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_phone_from_text(text: str) -> str | None:
    """Extract phone from text."""
    phone_pattern = r"\+91[-\s]?[0-9\*]{10}|\+[0-9]+-[0-9\*]+"
    match = re.search(phone_pattern, text)
    return match.group(0) if match else None


def _extract_email_from_text(text: str) -> str | None:
    """Extract email from text."""
    email_pattern = r"[a-zA-Z0-9._%\*+-]+@[a-zA-Z0-9.\*-]+\.[a-zA-Z]{2,}"
    match = re.search(email_pattern, text)
    return match.group(0) if match else None


def _extract_linkedin_from_text(text: str) -> str | None:
    """Extract LinkedIn URL from text."""
    linkedin_pattern = r"https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-]+"
    match = re.search(linkedin_pattern, text, re.IGNORECASE)
    return match.group(0) if match else None


def _get_empty_candidate() -> dict:
    """Return empty candidate with all required fields."""
    return _prepare_candidate_data({})


def format_postjobfree_resume_with_llm(raw_candidate: dict) -> dict:
    """
    Format scraped PostJobFree resume data into standardized schema using LLM.

    Args:
        raw_candidate: Raw candidate data from parser (may contain incomplete data)

    Returns:
        Formatted candidate dict matching MongoDB schema
    """
    try:
        settings = get_settings()

        if not settings.groq_api_key:
            logger.warning("groq_api_key_not_configured, using parser output as-is")
            return _prepare_candidate_data(raw_candidate)

        # Create system prompt for PostJobFree resume extraction
        system_prompt = SystemMessage(
            content="""You are an expert resume data extraction specialist. Your task is to clean, validate, and structure resume data from PostJobFree into a clean JSON format.

RULES:
1. Extract ONLY information that is clearly present in the raw text
2. Return NULL for missing fields, not guesses or assumptions
3. Distinguish between hard_skills (technical) and soft_skills (behavioral)
4. For dates, use YYYY-MM-DD format or null if not found
5. Remove duplicates from all arrays
6. Keep arrays concise - maximum 20 items per skill array

EXTRACTION GUIDELINES:
- candidate_name: Extract first clear name, remove titles/companies
- title: Current job title only
- summary: First 1-2 sentences of professional summary or about section
- hard_skills: Programming languages, frameworks, databases, tools (technical)
- soft_skills: Communication, leadership, agile, problem-solving (behavioral)
- experience: Array of jobs with company, dates, technologies, role
- projects: Array with title, description, tech stack
- education: Degree and course/specialization
- contact_phone: Phone number (including masked formats)
- candidate_email: Email address (including masked formats)

Return ONLY valid JSON, no additional text."""
        )

        # Prepare the user prompt
        user_prompt = HumanMessage(
            content=f"""Extract and format this PostJobFree resume data:

{json.dumps(raw_candidate, indent=2, default=str)}

Return a JSON object with these fields:
{{
  "candidate_name": "string or null",
  "title": "string or null",
  "summary": "string or null",
  "hard_skills": ["string"],
  "soft_skills": ["string"],
  "location": "string or null",
  "contact_phone": "string or null",
  "contact_linkedin_url": "string or null",
  "candidate_email": "string or null",
  "portfolio_url": "string or null",
  "experience": [
    {{
      "company_name": "string or null",
      "start_date": "YYYY-MM-DD or null",
      "end_date": "YYYY-MM-DD or null",
      "job_role": "string or null",
      "job_type": "full-time|part-time|contract or null",
      "technology": ["string"],
      "location": "string or null"
    }}
  ],
  "projects": [
    {{
      "title": "string or null",
      "description": "string or null",
      "technology_used": ["string"],
      "duration": "string or null"
    }}
  ],
  "education": [
    {{
      "degree": "string or null",
      "course": "string or null"
    }}
  ]
}}"""
        )

        # Call LLM
        logger.debug(
            "calling_llm_for_resume_formatting",
            candidate_name=raw_candidate.get("candidate_name"),
        )
        logger.debug("Raw candidate data:", json.dumps(raw_candidate, indent=2))
        try:
            # Initialize LLM
            llm = init_chat_model(
                model="openai/gpt-oss-120b",
                model_provider="groq",
                temperature=0,
                max_tokens=4000,
                api_key=settings.groq_api_key_tertiary,
            )
        except Exception as e:
            logger.error("failed_to_initialize_llm_with_primary_key", error=str(e))
            try:
                llm = init_chat_model(
                    model="openai/gpt-oss-120b",
                    model_provider="groq",
                    temperature=0,
                    max_tokens=4000,
                    api_key=settings.groq_api_key_secondary,
                )
            except Exception as e:
                logger.error(
                    "failed_to_initialize_llm_with_secondary_key", error=str(e)
                )
                llm = init_chat_model(
                    model="openai/gpt-oss-120b",
                    model_provider="groq",
                    temperature=0,
                    max_tokens=4000,
                    api_key=settings.groq_api_key,
                )
        response = llm.invoke([system_prompt, user_prompt])

        # Parse response
        response_text = response.content.strip()

        # Extract JSON from response (handle potential markdown code blocks)
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if not json_match:
            logger.warning("llm_response_invalid_json", response=response_text[:200])
            return _prepare_candidate_data(raw_candidate)

        formatted = json.loads(json_match.group(0))
        logger.info(
            "resume_formatted_with_llm", candidate_name=formatted.get("candidate_name")
        )
        logger.debug("Formatted candidate data:", json.dumps(formatted, indent=2))

        return _prepare_candidate_data(formatted)

    except Exception as e:
        logger.error(
            "failed_to_format_with_llm",
            error=str(e),
            candidate_name=raw_candidate.get("candidate_name"),
        )
        # Fall back to parser output
        return _prepare_candidate_data(raw_candidate)


def _prepare_candidate_data(candidate: dict) -> dict:
    """
    Prepare candidate data with proper defaults and structure.
    Ensures all required fields exist.
    """
    return {
        "candidate_name": candidate.get("candidate_name") or None,
        "title": candidate.get("title") or None,
        "summary": candidate.get("summary") or None,
        "hard_skills": candidate.get("hard_skills") or [],
        "soft_skills": candidate.get("soft_skills") or [],
        "location": candidate.get("location") or None,
        "contact_phone": candidate.get("contact_phone") or None,
        "contact_linkedin_url": candidate.get("contact_linkedin_url") or None,
        "candidate_email": candidate.get("candidate_email") or None,
        "portfolio_url": candidate.get("portfolio_url") or None,
        "experience": _prepare_experience(candidate.get("experience", [])),
        "projects": _prepare_projects(candidate.get("projects", [])),
        "education": _prepare_education(candidate.get("education", [])),
    }


def _prepare_experience(experience: list) -> list[dict]:
    """Prepare experience array with proper structure."""
    prepared = []

    for exp in experience:
        if not isinstance(exp, dict):
            continue

        prepared.append(
            {
                "company_name": exp.get("company_name") or None,
                "start_date": exp.get("start_date") or None,
                "end_date": exp.get("end_date") or None,
                "job_role": exp.get("job_role") or None,
                "job_type": exp.get("job_type") or None,
                "technology": exp.get("technology", [])
                if isinstance(exp.get("technology"), list)
                else [],
                "location": exp.get("location") or None,
            }
        )

    return prepared


def _prepare_projects(projects: list) -> list[dict]:
    """Prepare projects array with proper structure."""
    prepared = []

    for proj in projects:
        if not isinstance(proj, dict):
            continue

        prepared.append(
            {
                "title": proj.get("title") or None,
                "description": proj.get("description") or None,
                "technology_used": proj.get("technology_used", [])
                if isinstance(proj.get("technology_used"), list)
                else [],
                "duration": proj.get("duration") or None,
            }
        )

    return prepared


def _prepare_education(education: list) -> list[dict]:
    """Prepare education array with proper structure."""
    prepared = []

    for edu in education:
        if not isinstance(edu, dict):
            continue

        prepared.append(
            {
                "degree": edu.get("degree") or None,
                "course": edu.get("course") or None,
            }
        )

    return prepared

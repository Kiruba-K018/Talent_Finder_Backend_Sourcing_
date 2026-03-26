"""LLM-based candidate data formatting and enrichment."""

import json
import re

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from src.config.settings import get_settings
from src.observability.logging.logger import get_logger

logger = get_logger(__name__)


def format_candidate_with_llm(raw_candidate: dict) -> dict:
    """
    Format scraped candidate data into standardized schema using LLM.
    Aggressively cleans duplicated/garbled data from web scraping.

    Args:
        raw_candidate: Raw candidate data from parser (may contain duplicated/garbled content)

    Returns:
        Formatted candidate dict matching MongoDB schema
    """
    try:
        # Initialize settings
        settings = get_settings()

        # Initialize LLM
        llm = init_chat_model(
            model="openai/gpt-oss-120b",
            model_provider="groq",
            temperature=0,
            max_tokens=4000,
            api_key=settings.groq_api_key,
        )

        # Create AGGRESSIVE system prompt that handles garbled/duplicated data
        system_prompt = SystemMessage(
            content="""You are an expert data cleaner specializing in extracting clean, structured data from corrupted/duplicated web scraping content.

CRITICAL: Your primary job is to CLEAN AND DEDUPLICATE corrupted data, not preserve it as-is.

DATA CORRUPTION PATTERNS YOU WILL ENCOUNTER AND MUST FIX:
1. Duplicated text: "SightSpectrumSoftware Developer at SightSpectrum" → "Software Developer at SightSpectrum"
2. Mixed metadata: "4 yrs 2 mos Full-time On-site Software Developer" → Extract role, duration, job type separately
3. Concatenated fields: "WebSocket WebSocket Software Developer at SightSpectrum" → "Software Developer at SightSpectrum"
4. Malformed locations: "NodeJS SightSpectrum Chennai, Tamil Nadu, India" → "Chennai, Tamil Nadu, India"
5. Incomplete education: "Degree" → "Not specified" (keep generic if can't extract)
6. Empty descriptions needing extraction: Extract meaningful data from surrounding context

EXTRACTION RULES:

1. CANDIDATE NAME:
   - Remove job titles, company names, and location from candidate_name
   - Extract from title if present (first part before role keywords)
   - If only "Software Developer" type data, mark as empty

2. TITLE/POSITION:
   - Extract ONLY the job role (Engineer, Developer, Manager, etc.)
   - Remove dates, duration, employment type, location
   - Example: "Software Developer at SightSpectrum" NOT "Software Developer at SightSpectrum Full-time 4 yrs"

3. LOCATION:
   - Keep ONLY: "City, State/Country" or "City, Country"
   - Remove job titles, technology, metadata before/after
   - Example: "Chennai, Tamil Nadu, India" NOT "NodeJS SightSpectrum Chennai..."

4. DURATION EXTRACTION (Critical for projects):
   - Look for patterns: "X yrs Y mos", "X years", "X months", "Present"
   - Convert to readable format: "4 years 2 months" or "2 years" or "6 months"
   - Extract from ANY field (title, description, project details)
   - If "Present" or "On-going", mark as "Ongoing"

5. EXPERIENCE CLEANING:
   - company_name: ONLY company name, no dates/durations
   - job_role: ONLY role title, no company
   - Remove duplicate entries (same company + role = one entry)
   - Extract dates in format: "Feb 2023" → "2023-02-01", "Present" → ""
   - Extract job_type from metadata: Full-time, Part-time, Contract, Internship, Freelance

6. PROJECTS CLEANING - EXTRACT RICH DETAILS:
   - title: Project name ONLY, no metadata
   - description: Comprehensive description including:
     * What problem it solves
     * Technologies/tools used
     * Impact or outcomes achieved
     * Scale or scope (users, data volume, performance metrics)
   - duration: EXTRACT from description or title - this is CRITICAL
     Examples: "4 yrs 2 mos" → "4 years 2 months"
               "Feb 2023 - Present · 3 yrs 2 mos" → "3 years 2 months"
   - technology_used: List all technologies, frameworks, platforms, databases mentioned

7. EXPERIENCE CLEANING - EXTRACT RICH DETAILS:
   - company_name: Company name ONLY, no dates/durations
   - job_role: Full role title with seniority if present (e.g., "Senior Software Engineer")
   - start_date: Extract date from ANY format to "YYYY-MM-DD"
   - end_date: Extract date or "Present" if ongoing
   - job_type: Full-time, Part-time, Contract, Internship, Freelance, Permanent, or empty
   - technology: All technologies, programming languages, frameworks, tools used
   - EXTRACT HIDDEN DETAILS:
     * Achievement metrics (% improvement, users, revenue impact)
     * Notable accomplishments or projects led
     * Team size managed if applicable
     * Key technologies or domains
     * Scope of work (infrastructure, product, platform, team building)

8. EDUCATION CLEANING - EXTRACT RICH DETAILS:
   - degree: Full degree name (B.Tech, M.Sc, Bachelor of Science, Master of Arts, Ph.D., etc.)
   - course: Major/specialization/field of study (Data Science, Mechanical Engineering, etc.)
   - EXTRACT IF PRESENT:
     * University/Institution name
     * Graduation year (YYYY format)
     * GPA or honors (First Class, Distinction, 8.5/10, etc.)
     * Relevant coursework (Machine Learning, Distributed Systems, etc.)
     * Any additional achievements or awards

9. CERTIFICATIONS CLEANING - EXTRACT RICH DETAILS:
   - certification_name: Full certification name
   - related_technology: Technologies covered by certification
   - EXTRACT IF PRESENT:
     * Issuing organization (Google, AWS, Microsoft, etc.)
     * Issue date (YYYY-MM-DD or just year)
     * Expiry date if applicable
     * Credential ID or URL
     * Verification link

10. SKILLS:
   - hard_skills: Technical skills only (Python, React, AWS, SQL, Kubernetes, etc.)
   - soft_skills: Interpersonal skills (Leadership, Communication, Problem-solving, etc.)
   - Remove buzzwords: "passionate", "enthusiastic", "highly motivated", "driven", "dynamic", etc.

11. DEDUPLICATION & CLEANUP:
   - Remove duplicated strings from fields
   - Consolidate similar entries (e.g., "Python", "python", "Python 3" → "Python")
   - Remove markdown formatting, HTML encoding, excessive whitespace

OUTPUT FORMAT:
- Return ONLY valid JSON, no markdown formatting
- All date strings: "YYYY-MM-DD" format or empty string ""
- All arrays: use [] if empty
- All optional strings: use "" if empty
- Preserve data integrity while cleaning formatting/duplication
- MAXIMALLY EXTRACT ALL AVAILABLE INFORMATION FROM THE DATA"""
        )

        # Create user prompt with candidate data
        user_prompt = HumanMessage(
            content=f"""CLEAN, ENRICH, AND EXTRACT COMPREHENSIVE DETAILS from this candidate data:

Raw Scraped Data:
{json.dumps(raw_candidate, indent=2)}

CRITICAL INSTRUCTIONS: 
- Extract ALL embedded/hidden details (achievements, metrics, dates, organizations)
- Aggressively remove duplicated text 
- Extract duration from ANY field (descriptions, titles, metadata)
- Clean up concatenated/malformed fields
- For EXPERIENCE: Extract company, role, dates, technologies AND achievements/metrics if present
- For PROJECTS: Extract comprehensive descriptions with impact and all technologies
- For EDUCATION: Extract degree, course AND university, graduation year, GPA/honors if available
- For CERTIFICATIONS: Extract name, technology AND issuer, dates, credential URL if available
- Return ONLY valid JSON with MAXIMUM detail extraction:

{{
  "candidate_name": "string (cleaned, no job titles)",
  "title": "string (job role only, no company/dates)",
  "summary": "string (removed buzzwords, cleaned)",
  "location": "string (City, Country format, cleaned)",
  "contact_phone": "string or empty",
  "candidate_email": "string or empty",
  "contact_linkedin_url": "string or empty",
  "portfolio_url": "string or empty",
  "hard_skills": ["tech1", "tech2"],
  "soft_skills": ["skill1", "skill2"],
  "languages_known": ["lang1"],
  "volunteer_works": ["volunteer1"],
  "publications": ["pub1"],
  "experience": [
    {{
      "company_name": "string (company only, no dates)",
      "job_role": "string (full role title with seniority)",
      "start_date": "YYYY-MM-DD or empty",
      "end_date": "YYYY-MM-DD or empty",
      "job_type": "Full-time|Part-time|Contract|Internship|Freelance|Permanent or empty",
      "technology": ["tech1", "tech2"],
      "achievements": "string (key achievements, metrics, or outcomes if present in data)"
    }}
  ],
  "projects": [
    {{
      "title": "string (project name, not duplicated)",
      "description": "string (comprehensive: problem solved, impact, achievements, scale, technologies)",
      "technology_used": ["tech1", "tech2"],
      "duration": "string (EXTRACT: '4 years 2 months' or '18 months' or '')",
      "metrics": "string (performance, scale, users, or impact metrics if available)"
    }}
  ],
  "education": [
    {{
      "degree": "B.Tech|M.Sc|Bachelor|Master|Ph.D.|string or empty",
      "course": "string (major/field/specialization or empty)",
      "university": "string (institution name if available)",
      "graduation_year": "YYYY or empty",
      "gpa_honors": "string (GPA, honors, or distinction if available)"
    }}
  ],
  "certifications": [
    {{
      "certification_name": "string",
      "related_technology": ["tech1", "tech2"],
      "issuer": "string (issuing organization if available)",
      "issue_date": "YYYY-MM-DD or YYYY or empty",
      "expiry_date": "YYYY-MM-DD or empty",
      "credential_url": "string (URL to credential/verification if available)"
    }}
  ]
}}"""
        )

        # Call LLM
        logger.debug("Calling LLM to format and clean candidate data")
        response = llm.invoke([system_prompt, user_prompt])

        # Parse response
        response_text = response.content.strip()

        # Extract JSON from response (in case LLM adds markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        formatted_data = json.loads(response_text)
        logger.info(
            f"Successfully formatted and cleaned candidate: {formatted_data.get('candidate_name', 'Unknown')}"
        )
        return formatted_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
        logger.debug(
            f"Response was: {response_text if 'response_text' in locals() else 'N/A'}"
        )
        # Return fallback format on failure
        return _fallback_format(raw_candidate)

    except Exception as e:
        logger.error(f"Error formatting candidate with LLM: {str(e)}")
        # Return fallback format on failure
        return _fallback_format(raw_candidate)


def _fallback_format(raw_candidate: dict) -> dict:
    """Fallback formatting if LLM fails - maps raw data to schema with aggressive cleaning."""

    # Helper to extract duration from text
    def extract_duration(text: str) -> str:
        """Extract duration pattern from text like '4 yrs 2 mos' or 'Feb 2023 - Present'."""
        if not text:
            return ""

        # Pattern: "X yrs Y mos" or "X years Y months"
        duration_match = re.search(r"(\d+)\s*yrs?\s+(\d+)\s*mos?", text, re.IGNORECASE)
        if duration_match:
            years, months = duration_match.groups()
            return f"{years} years {months} months"

        # Pattern: "X yrs" or "X years"
        duration_match = re.search(r"(\d+)\s*yrs?(?:\s|$)", text, re.IGNORECASE)
        if duration_match:
            years = duration_match.group(1)
            return f"{years} years"

        # Pattern: "X months" or "X mos"
        duration_match = re.search(r"(\d+)\s*mos?(?:\s|$)", text, re.IGNORECASE)
        if duration_match:
            months = duration_match.group(1)
            return f"{months} months"

        # Check for "Present" or "Ongoing"
        if re.search(r"\bpresent\b|\bongoing\b", text, re.IGNORECASE):
            return "Ongoing"

        return ""

    # Helper to clean duplicated text
    def clean_duplicates(text: str) -> str:
        """Remove duplicated sequences from text."""
        if not text:
            return ""

        # Split by common separators and remove duplicates while preserving order
        words = re.split(r"\s+", text)
        cleaned = []
        prev_words = set()

        for word in words:
            # Keep word if it's not part of a repeated sequence
            if word not in prev_words:
                cleaned.append(word)
            prev_words.add(word)

            # Clear previous tracking every few words to allow legitimate repeats
            if len(cleaned) % 10 == 0:
                prev_words = set()

        return " ".join(cleaned).strip()

    # Helper to extract clean location
    def clean_location(location: str) -> str:
        """Extract clean location (City, Country) from messy text."""
        if not location:
            return ""

        # Remove common tech/job keywords that get mixed in
        location = re.sub(
            r"\b(NodeJS|Python|JavaScript|React|Software|Developer|Engineer|Full-time|Part-time)\b",
            "",
            location,
            flags=re.IGNORECASE,
        )

        # Find comma-separated location pattern
        match = re.search(r"([A-Za-z\s]+),\s*([A-Za-z\s,]+?)(?:\s*$|[\n·])", location)
        if match:
            return f"{match.group(1)}, {match.group(2)}".strip()

        return location.strip()

    # Helper to clean title
    def clean_title(title: str) -> str:
        """Extract clean job title from messy text."""
        if not title:
            return ""

        # Remove dates, durations, employment type
        title = re.sub(r"\d{4}.*?(?:·|$)", "", title)  # Remove from 4-digit year onward
        title = re.sub(
            r"(?:Full-time|Part-time|Contract|Freelance|Internship|On-site|Remote).*?(?:·|$)",
            "",
            title,
            flags=re.IGNORECASE,
        )
        title = re.sub(
            r"\d+\s*(?:yrs?|mos?|months?|years?).*", "", title, flags=re.IGNORECASE
        )  # Remove duration

        # Keep only meaningful part (first 1-5 words, usually the job role)
        words = title.split()[:5]
        return " ".join(words).strip()

    return {
        "candidate_name": clean_duplicates(raw_candidate.get("name", "")),
        "title": clean_title(raw_candidate.get("title", "")),
        "summary": _clean_text(raw_candidate.get("summary", "")),
        "location": clean_location(raw_candidate.get("location", "")),
        "contact_phone": raw_candidate.get("phone", ""),
        "candidate_email": raw_candidate.get("email", ""),
        "contact_linkedin_url": raw_candidate.get("profile_url", ""),
        "portfolio_url": "",
        "hard_skills": raw_candidate.get("hard_skills", []),
        "soft_skills": raw_candidate.get("soft_skills", []),
        "languages_known": [],
        "volunteer_works": [],
        "publications": [],
        "experience": [
            {
                "company_name": clean_duplicates(exp.get("company_name", "")),
                "job_role": clean_duplicates(exp.get("job_role", "")),
                "start_date": exp.get("start_date", ""),
                "end_date": exp.get("end_date", ""),
                "job_type": exp.get("job_type", ""),
                "technology": exp.get("technology", []),
                "achievements": exp.get("achievements", ""),
            }
            for exp in raw_candidate.get("experience", [])
        ],
        "projects": [
            {
                "title": clean_duplicates(proj.get("title", "")),
                "description": _clean_text(
                    clean_duplicates(proj.get("description", ""))
                ),
                "technology_used": proj.get("technology_used", []),
                "duration": extract_duration(
                    proj.get("description", "")
                    or proj.get("title", "")
                    or proj.get("duration", "")
                ),
                "metrics": proj.get("metrics", ""),
            }
            for proj in raw_candidate.get("projects", [])
        ],
        "education": [
            {
                "degree": edu.get("degree", ""),
                "course": edu.get("course", ""),
                "university": edu.get("university", ""),
                "graduation_year": edu.get("graduation_year", ""),
                "gpa_honors": edu.get("gpa_honors", ""),
            }
            for edu in raw_candidate.get("education", [])
        ],
        "certifications": [
            {
                "certification_name": cert.get("certification_name", ""),
                "related_technology": cert.get("related_technology", []),
                "issuer": cert.get("issuer", ""),
                "issue_date": cert.get("issue_date", ""),
                "expiry_date": cert.get("expiry_date", ""),
                "credential_url": cert.get("credential_url", ""),
            }
            for cert in raw_candidate.get("certifications", [])
        ],
    }


def _clean_text(text: str) -> str:
    """Remove buzzwords, emojis, and corrupted patterns from text."""
    if not text:
        return ""

    # Remove common buzzwords and corporate jargon
    buzzwords = [
        "passionate",
        "enthusiastic",
        "highly motivated",
        "driven",
        "dynamic",
        "results-oriented",
        "self-starter",
        "team player",
        "synergy",
        "paradigm",
        "leverage",
        "circle back",
        "touch base",
        "thinking outside the box",
        "low-hanging fruit",
        "move the needle",
        "deep dive",
        "bandwidth",
        "ping",
        "deck",
        "boil the ocean",
        "strong",
        "proven",
        "extensive",
        "extensive experience",
        "proficient",
        "expert",
        "specialist",
        "dedicated",
        "flexible",
        "innovative",
        "creative",
        "proactive",
        "detail-oriented",
        "goal-oriented",
        "ambitious",
        "hard-working",
        "committed",
        "responsible",
        "skilled",
        "able",
        "capable",
        "experienced",
    ]

    for buzzword in buzzwords:
        # Replace buzzword with empty string (case-insensitive)
        text = re.sub(rf"\b{buzzword}\b", "", text, flags=re.IGNORECASE)

    # Remove emojis
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f1e0-\U0001f1ff"  # flags (iOS)
        "]+",
        flags=re.UNICODE,
    )
    text = emoji_pattern.sub(r"", text)

    # Remove corrupted duplicate patterns (e.g., "Word Word Word", "Phrase Phrase")
    # This handles cases where HTML scraping produces repeated tokens
    words = text.split()
    cleaned_words = []
    skip_count = 0

    for i, word in enumerate(words):
        if skip_count > 0:
            skip_count -= 1
            continue

        # Check if current word repeats in next positions
        repetitions = 1
        j = i + 1
        while j < len(words) and j < i + 3 and words[j] == word:
            repetitions += 1
            j += 1

        # Add word only once even if repeated
        if repetitions > 1:
            cleaned_words.append(word)
            skip_count = repetitions - 1
        else:
            cleaned_words.append(word)

    text = " ".join(cleaned_words)

    # Clean up extra spaces and special characters
    text = " ".join(text.split())

    # Remove trailing/leading punctuation and spaces
    text = re.sub(r"^[\s\-·•]+|[\s\-·•]+$", "", text)

    return text.strip()

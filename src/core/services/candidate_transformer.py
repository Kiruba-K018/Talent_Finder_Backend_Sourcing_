"""
Transform parsed candidate data into the exact MongoDB schema format.
Adds UUIDs, timestamps, and required fields to match the data model.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from src.utils.hashing import compute_identity_hash, compute_profile_hash
from src.observability.logging.logger import get_logger

logger = get_logger(__name__)


def transform_candidate_to_schema(
    parsed_candidate: Dict[str, Any],
    candidate_id: str = None,
    hash_value: str = None,
    org_id: str = None,
) -> Dict[str, Any]:
    """
    Transform parsed LinkedIn candidate data into the exact MongoDB schema.
    
    Generates:
    - _id: MongoDB object ID (hex string)
    - candidate_id: UUID for candidate
    - hash: Identity hash for deduplication
    - IDs for all nested objects (experience_id, education_id, etc.)
    - Timestamps: sourced_at, updated_on
    - Required fields with defaults
    - parsed_resume_data section
    
    Args:
        parsed_candidate: Raw candidate dict from parser
        candidate_id: Optional UUID for candidate
        hash_value: Optional hash for deduplication
        org_id: Organization ID for tracking
    
    Returns:
        Complete candidate document in MongoDB schema format
    """
    
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # Generate IDs if not provided
    _id = str(uuid.uuid4()).replace("-", "")[:24]  # MongoDB ObjectID format
    if not candidate_id:
        candidate_id = str(uuid.uuid4())
    
    resume_id = str(uuid.uuid4())
    platform_id = str(uuid.uuid4())
    source_run_id = str(uuid.uuid4())
    
    # Compute hash if not provided
    if not hash_value:
        hash_value = compute_identity_hash(
            parsed_candidate.get("name", ""),
            parsed_candidate.get("email", ""),
            parsed_candidate.get("location", ""),
            profile_url=parsed_candidate.get("profile_url", ""),
        )
    
    # Transform experience array with experience_id
    experience = []
    for idx, exp in enumerate(parsed_candidate.get("experience", [])):
        transformed_exp = {
            "experience_id": str(uuid.uuid4()),
            "candidate_id": _id,  # Use MongoDB _id, not UUID candidate_id
            "company_name": exp.get("company_name", ""),
            "start_date": exp.get("start_date", ""),
            "end_date": exp.get("end_date", ""),
            "technology": exp.get("technology", []),
            "job_role": exp.get("job_role", ""),
            "job_type": exp.get("job_type", ""),
        }
        # Remove empty location if not present
        if exp.get("location"):
            transformed_exp["location"] = exp["location"]
        experience.append(transformed_exp)
    
    # Transform education array with education_id
    education = []
    for edu in parsed_candidate.get("education", []):
        transformed_edu = {
            "education_id": str(uuid.uuid4()),
            "candidate_id": _id,
            "degree": edu.get("degree", ""),
            "course": edu.get("course", ""),
        }
        # Add optional fields if present
        if edu.get("school_name"):
            transformed_edu["school_name"] = edu["school_name"]
        if edu.get("graduation_year"):
            transformed_edu["graduation_year"] = edu["graduation_year"]
        education.append(transformed_edu)
    
    # Transform certifications array with certification_id
    certifications = []
    for cert in parsed_candidate.get("certifications", []):
        transformed_cert = {
            "certification_id": str(uuid.uuid4()),
            "candidate_id": _id,
            "certification_name": cert.get("certification_name", ""),
            "related_technology": cert.get("related_technology", []),
        }
        # Add optional fields if present
        if cert.get("issuer"):
            transformed_cert["issuer"] = cert["issuer"]
        if cert.get("issue_date"):
            transformed_cert["issue_date"] = cert["issue_date"]
        certifications.append(transformed_cert)
    
    # Transform projects array with project_id
    projects = []
    for proj in parsed_candidate.get("projects", []):
        transformed_proj = {
            "project_id": str(uuid.uuid4()),
            "candidate_id": _id,
            "title": proj.get("title", ""),
            "description": proj.get("description", ""),
            "technology_used": proj.get("technology_used", []),
            "duration": proj.get("duration", ""),
        }
        projects.append(transformed_proj)
    
    # Prepare soft skills
    soft_skills = parsed_candidate.get("soft_skills", [])
    if not soft_skills:
        # Extract soft skills from summary/title if not present
        text = f"{parsed_candidate.get('title', '')} {parsed_candidate.get('summary', '')}".lower()
        soft_skills_keywords = [
            "Leadership", "Communication", "Mentorship", "Scrum", "Team Collaboration",
            "Time Management", "Problem-Solving", "Teamwork", "Project Management",
            "Strategic Thinking", "Stakeholder Management", "Agile", "Kanban"
        ]
        soft_skills = [s for s in soft_skills_keywords if s.lower() in text]
    
    # Extract languages known (if available in summary)
    languages_known = extract_languages(parsed_candidate.get("summary", ""))
    
    # If summary is empty, try to create one from title and experience
    summary = parsed_candidate.get("summary", "")
    if not summary or len(summary.strip()) == 0:
        # Build a summary from available data
        title = parsed_candidate.get("title", "")
        location = parsed_candidate.get("location", "")
        experience_list = parsed_candidate.get("experience", [])
        
        if title or location or experience_list:
            summary_parts = []
            if title:
                summary_parts.append(f"Professional: {title}")
            if location:
                summary_parts.append(f"Based in {location}")
            if experience_list:
                companies = [exp.get("company_name", "") for exp in experience_list[:3] if exp.get("company_name")]
                if companies:
                    summary_parts.append(f"Experience at: {', '.join(companies)}")
            summary = " | ".join(summary_parts) if summary_parts else ""
    
    logger.info(f"Summary extracted: {len(summary)} chars")
    
    # Build the complete candidate document
    candidate_document = {
        "_id": _id,
        "candidate_id": candidate_id,  # UUID for external reference
        "hash": hash_value,
        "candidate_name": parsed_candidate.get("name", ""),
        "resume_id": resume_id,
        "platform_id": platform_id,
        "sourced_at": now_iso,
        "source_run_id": source_run_id,
        "job_id": None,  # Will be set later during shortlisting
        "updated_on": now_iso,
        "title": parsed_candidate.get("title", ""),
        "summary": summary,
        "hard_skills": parsed_candidate.get("hard_skills", []),
        "soft_skills": soft_skills,
        "languages_known": languages_known,
        "volunteer_works": parsed_candidate.get("volunteer_works", []),
        "publications": parsed_candidate.get("publications", []),
        "location": parsed_candidate.get("location", ""),
        "contact_phone": parsed_candidate.get("phone", ""),
        "contact_linkedin_url": parsed_candidate.get("profile_url", ""),
        "candidate_email": parsed_candidate.get("email", ""),
        "portfolio_url": None,
        "experience": experience,
        "projects": projects,
        "education": education,
        "certifications": certifications,
        # Parsed resume data mirrors the main document structure
        "parsed_resume_data": {
            "candidate_id": candidate_id,
            "candidate_name": parsed_candidate.get("name", ""),
            "title": parsed_candidate.get("title", ""),
            "summary": summary,
            "experience": experience,
            "projects": projects,
            "education": education,
            "certifications": certifications,
            "hard_skills": parsed_candidate.get("hard_skills", []),
            "soft_skills": soft_skills,
            "languages_known": languages_known,
        },
    }
    
    logger.info(
        "candidate_transformed",
        candidate_id=candidate_id,
        name=candidate_document["candidate_name"],
        experience_count=len(experience),
        education_count=len(education),
    )
    
    return candidate_document


def extract_languages(text: str) -> List[str]:
    """Extract language names from text."""
    languages_keywords = {
        "spanish": ["spanish", "español"],
        "tamil": ["tamil"],
        "hindi": ["hindi"],
        "english": ["english"],
        "french": ["french", "français"],
        "german": ["german", "deutsch"],
        "russian": ["russian", "русский"],
        "chinese": ["chinese", "mandarin", "cantonese", "中文"],
        "japanese": ["japanese", "日本語"],
        "korean": ["korean", "한국어"],
        "portuguese": ["portuguese", "português"],
        "italian": ["italian", "italiano"],
        "dutch": ["dutch", "nederlands"],
        "swedish": ["swedish", "svenska"],
        "polish": ["polish", "polski"],
        "turkish": ["turkish", "türkçe"],
        "bengali": ["bengali", "বাংলা"],
        "urdu": ["urdu", "اردو"],
        "arabic": ["arabic", "العربية"],
        "hebrew": ["hebrew", "עברית"],
        "thai": ["thai", "ไทย"],
        "vietnamese": ["vietnamese", "tiếng việt"],
    }
    
    text_lower = text.lower()
    found_languages = []
    
    for lang, keywords in languages_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                # Capitalize first letter for display
                found_languages.append(lang.capitalize())
                break
    
    return sorted(list(set(found_languages)))

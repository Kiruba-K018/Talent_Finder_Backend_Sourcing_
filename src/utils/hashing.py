import hashlib


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compute_identity_hash(name: str = None, email: str = None, location: str = None, profile_url: str = "") -> str:
    """Detects duplicate profiles across platforms.
    
    Handles None values gracefully by converting to empty strings.
    
    Priority:
    1. LinkedIn profile URL (most unique)
    2. Email + Name (if email exists)
    3. Name + Location fallback
    
    Args:
        name: Candidate name (optional)
        email: Candidate email (optional)
        location: Candidate location (optional)
        profile_url: LinkedIn profile URL (optional)
    
    Returns:
        SHA256 hash of the identity string
    """
    # Ensure values are strings, not None
    name = (name or "").strip().lower()
    email = (email or "").strip().lower()
    location = (location or "").strip().lower()
    profile_url = (profile_url or "").strip().lower()
    
    # LinkedIn URL is the strongest identifier
    if profile_url and "linkedin.com" in profile_url:
        normalized = profile_url
    # If email exists, use it as strong identifier
    elif email:
        normalized = f"{name}|{email}"
    # Fallback to name + location
    elif name and location:
        normalized = f"{name}|{location}"
    # Last resort: just use name if anything is available
    elif name:
        normalized = name
    elif email:
        normalized = email
    else:
        # If nothing is available, create a placeholder hash
        normalized = "unknown"
    
    return _sha256(normalized)


def compute_profile_hash(
    skills: list[str] = None,
    education: list[dict] = None,
    experience: list[dict] = None,
    certifications: list[str] = None,
) -> str:
    """Detects profile updates since last scrape.
    
    Handles None and empty values gracefully.
    
    Args:
        skills: List of hard skills (technical)
        education: List of education records
        experience: List of work experience records
        certifications: List of certifications
    
    Returns:
        SHA256 hash of the profile profile
    """
    # Handle None values by converting to empty lists
    skills = [s for s in (skills or []) if s]  # Filter out None and empty strings
    education = [e for e in (education or []) if e]
    experience = [e for e in (experience or []) if e]
    certifications = [c for c in (certifications or []) if c]
    
    skills_str   = ",".join(sorted(s.lower() if isinstance(s, str) else str(s) for s in skills))
    edu_str      = str(sorted(str(e) for e in education))
    exp_str      = str(sorted(str(e) for e in experience))
    certs_str    = ",".join(sorted(c.lower() if isinstance(c, str) else str(c) for c in certifications))
    combined     = f"{skills_str}|{edu_str}|{exp_str}|{certs_str}"
    return _sha256(combined)
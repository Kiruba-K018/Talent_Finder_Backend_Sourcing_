import hashlib


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compute_identity_hash(name: str, email: str, location: str, profile_url: str = "") -> str:
    """Detects duplicate profiles across platforms.
    
    Priority:
    1. LinkedIn profile URL (most unique)
    2. Email + Name (if email exists)
    3. Name + Location fallback
    """
    # LinkedIn URL is the strongest identifier
    if profile_url and "linkedin.com" in profile_url.lower():
        # Extract unique LinkedIn username from URL
        normalized = profile_url.strip().lower()
    # If email exists, use it as strong identifier
    elif email and email.strip():
        normalized = f"{name.strip().lower()}|{email.strip().lower()}"
    # Fallback to name + location
    else:
        normalized = f"{name.strip().lower()}|{location.strip().lower()}"
    
    return _sha256(normalized)


def compute_profile_hash(
    skills: list[str],
    education: list[dict],
    experience: list[dict],
    certifications: list[str],
) -> str:
    """Detects profile updates since last scrape."""
    skills_str   = ",".join(sorted(s.lower() for s in skills))
    edu_str      = str(sorted(str(e) for e in education))
    exp_str      = str(sorted(str(e) for e in experience))
    certs_str    = ",".join(sorted(c.lower() for c in certifications))
    combined     = f"{skills_str}|{edu_str}|{exp_str}|{certs_str}"
    return _sha256(combined)
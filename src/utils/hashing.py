import hashlib


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compute_identity_hash(name: str, email: str, location: str) -> str:
    """Detects duplicate profiles across platforms."""
    normalized = f"{name.strip().lower()}|{email.strip().lower()}|{location.strip().lower()}"
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
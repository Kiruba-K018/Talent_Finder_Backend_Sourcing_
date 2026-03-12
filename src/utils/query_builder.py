def build_google_search_query(skills: list[str], location: str) -> str:
    """
    Produces: site:linkedin.com/in "python developer" "django" "san francisco"
    """
    skills_str = " ".join(f'"{s}"' for s in skills[:3])   # top 3 to keep query focused
    location_str = f'"{location}"' if location else ""
    parts = [f"site:linkedin.com/in", skills_str, location_str]
    return " ".join(filter(None, parts))
def build_google_search_query(skills: list[str], location: str) -> str:
    """
    Builds a LinkedIn search query from skills and location.
    Returns keywords formatted for direct LinkedIn search.
    
    Example:
        Input: skills=["python", "django"], location="san francisco"
        Output: "python django"
    """
    if not skills:
        return "developer"
    
    # Join top 3 skills for LinkedIn search (space-separated, no quotes for LinkedIn search)
    skills_str = " ".join(skills[:3])
    return skills_str
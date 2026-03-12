from typing import TypedDict

class ExperienceEntry(TypedDict):
    company_name: str
    role: str
    start_date: str
    end_date: str
    technologies: list[str]

class EducationEntry(TypedDict):
    institution: str
    degree: str
    field: str
    graduation_year: str

class CandidateDocument(TypedDict):
    _id:              str          # candidate_id (UUID str)
    name:             str
    email:            str
    phone:            str
    location:         str
    title:            str
    summary:          str
    hard_skills:      list[str]
    soft_skills:      list[str]
    experience:       list[ExperienceEntry]
    education:        list[EducationEntry]
    certifications:   list[str]
    projects:         list[dict]
    profile_url:      str
    source_platform:  str
    hash_identity:    str
    hash_profile:     str
    created_at:       str
    updated_at:       str
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ManualTriggerRequest(BaseModel):
    config_id: UUID
    max_profiles: int | None = None


class TriggerResponse(BaseModel):
    message: str
    config_id: str
    status: str


class HealthCheckResponse(BaseModel):
    status: str
    service: str


class HealthReadinessResponse(BaseModel):
    status: str
    checks: dict


class DryRunQueryResponse(BaseModel):
    config_id: str
    org_id: str
    query: str
    search_skills: list[str]
    search_location: str
    max_profiles: int
    frequency: str


class CandidateInsertResponse(BaseModel):
    message: str
    candidate_id: str


class CandidateFindResponse(BaseModel):
    candidate_name: str | None = None
    title: str | None = None
    found: bool = False


class CandidateUpdateResponse(BaseModel):
    message: str
    matched_count: int = 0


class CandidateIndexResponse(BaseModel):
    message: str
    indexes_created: bool


class SourcingConfigBaseResponse(BaseModel):
    id: UUID
    org_id: UUID
    is_active: bool
    frequency: str
    scheduled_time: str | None = None
    scheduled_day: str | None = None
    search_skills: list[str]
    search_location: str
    max_profiles: int
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime
    created_by: UUID

    class Config:
        from_attributes = True


class SourcingConfigFetchActiveResponse(BaseModel):
    configs: list[SourcingConfigBaseResponse]
    total: int = 0


class SourcingConfigFetchDueResponse(BaseModel):
    configs: list[SourcingConfigBaseResponse]
    total: int = 0


class SourcingConfigFetchByIdResponse(BaseModel):
    id: UUID
    org_id: UUID
    is_active: bool
    frequency: str
    scheduled_time: str | None = None
    scheduled_day: str | None = None
    search_skills: list[str]
    search_location: str
    max_profiles: int
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime
    created_by: UUID

    class Config:
        from_attributes = True


class SourcingConfigUpdateTimestampsResponse(BaseModel):
    message: str
    config_id: str
    last_run_at: datetime
    next_run_at: datetime

from pydantic import BaseModel
from uuid import UUID

class ManualTriggerRequest(BaseModel):
    config_id: UUID
    max_profiles: int | None = None   # optional override


class TriggerResponse(BaseModel):
    message: str
    config_id: str
    status: str

# Pipeline stage names — used in logs, traces and metrics
STAGE_SCHEDULER       = "scheduler"
STAGE_SCRAPING        = "scraping"
STAGE_PARSING         = "parsing"
STAGE_HASHING         = "hashing"
STAGE_DEDUP           = "deduplication"
STAGE_INSERTION       = "insertion"
STAGE_EMBEDDING       = "embedding"

# Duplicate decision outcomes
OUTCOME_INSERT        = "insert"
OUTCOME_UPDATE        = "update"
OUTCOME_SKIP          = "skip"

# HTTP
INTERNAL_CANDIDATES_PATH = "api/v1/sourced-candidates/"

# Chroma
CHROMA_COLLECTION_NAME   = "candidate_skills_embeddings"

# Scheduler
DEFAULT_POLL_INTERVAL    = 60  # seconds
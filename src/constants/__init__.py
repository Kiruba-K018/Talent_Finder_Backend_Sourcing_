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
INTERNAL_SOURCE_RUNS_PATH = "api/v1/source-runs/"

# LinkedIn Platform ID (constant for all scraping operations)
LINKEDIN_PLATFORM_ID = "11000015-0000-0000-0000-000000000001"

# Chroma
CHROMA_COLLECTION_NAME   = "candidate_skills_embeddings"

# Scheduler
DEFAULT_POLL_INTERVAL    = 60  # seconds
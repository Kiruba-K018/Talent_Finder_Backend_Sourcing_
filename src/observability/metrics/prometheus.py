from prometheus_client import Counter, Histogram, start_http_server
from src.config.settings import get_settings

scrape_jobs_total = Counter(
    "scrape_jobs_total",
    "Total scrape jobs triggered",
    ["org_id", "status"],
)

scrape_failures_total = Counter(
    "scrape_failures_total",
    "Total scrape job failures",
    ["org_id", "reason"],
)

candidates_extracted_total = Counter(
    "candidates_extracted_total",
    "Total candidates extracted",
    ["org_id"],
)

duplicates_detected_total = Counter(
    "duplicates_detected_total",
    "Total duplicate candidates detected",
    ["outcome"],   # "update" | "skip"
)

pipeline_duration_seconds = Histogram(
    "pipeline_duration_seconds",
    "End-to-end pipeline duration per candidate",
    ["stage"],
)


def start_metrics_server() -> None:
    settings = get_settings()
    start_http_server(settings.prometheus_port)
from prometheus_client import Counter, Histogram

REQUESTS_TOTAL = Counter(
    "cooking_agent_requests_total",
    "Total number of processed user requests",
    ["channel", "result"],
)

ANSWER_PATH_TOTAL = Counter(
    "cooking_agent_answer_path_total",
    "How responses were produced",
    ["path"],
)

REQUEST_LATENCY_SECONDS = Histogram(
    "cooking_agent_request_latency_seconds",
    "End-to-end request latency in seconds",
    ["channel"],
    buckets=(0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1, 1.5, 2, 3, 5, 8, 13),
)

SEARCH_HITS_TOTAL = Counter(
    "cooking_agent_search_hits_total",
    "Number of recipes found per search source",
    ["source"],
)

STAGE_DURATION_SECONDS = Histogram(
    "cooking_agent_stage_duration_seconds",
    "Duration of individual pipeline stages in seconds",
    ["stage"],
    buckets=(0.01, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10),
)

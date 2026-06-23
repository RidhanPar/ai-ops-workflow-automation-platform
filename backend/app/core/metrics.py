from prometheus_client import Counter, Histogram

# Total agent invocations, labelled by which analysis path was taken.
# Labels: source (openai_structured_output | local_fallback_rules |
#         fallback_invalid_output | fallback_provider_failure |
#         fallback_unexpected_failure)
agentic_requests_total = Counter(
    "agentic_requests_total",
    "Total number of LangGraph agent invocations",
    ["source"],
)

# Latency of each LLM analysis call in seconds.
# The histogram uses finer buckets at the low end because the local fallback
# completes in milliseconds while real OpenAI calls can take several seconds.
llm_call_latency_seconds = Histogram(
    "llm_call_latency_seconds",
    "Per-LLM-call latency in seconds",
    ["source"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0),
)

# Cumulative token count broken down by direction.
# Labels: direction (input | output)
llm_tokens_used_total = Counter(
    "llm_tokens_used_total",
    "Cumulative LLM token count",
    ["direction"],
)

# Number of times a human approval gate was opened, by what triggered it.
# Labels: action_type (agent_update_ticket | workflow_escalate |
#         approval_required)
human_approval_gates_triggered_total = Counter(
    "human_approval_gates_triggered_total",
    "Total number of human approval gate triggers",
    ["action_type"],
)

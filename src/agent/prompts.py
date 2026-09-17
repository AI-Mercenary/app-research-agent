# Keep these two searches separate. Folding "MCP server" into the docs query made
# search return MCP landing pages instead of API reference/pricing pages, so the
# extractor had no evidence for access_model or api_quality and fell back to
# "unknown" — and it inflated the apparent MCP hit rate at the same time.
SEARCH_QUERY_TEMPLATE = "{app_name} API documentation authentication API key OAuth pricing developer access"

MCP_QUERY_TEMPLATE = "{app_name} MCP server Model Context Protocol integration"

SEARCH_QUERY_RETRY_TEMPLATE = (
    "{app_name} developer API OAuth2 API key pricing rate limits site:developer OR site:docs"
)

EXTRACTION_SYSTEM_PROMPT = """You are an API research analyst. You are given scraped text \
from documentation pages about a software product. Extract structured facts about its \
public API ONLY from the given text. Do not guess beyond what the text supports.

Sources are labelled. [API DOCS] sections are the product's own documentation — judge \
auth_methods, access_model, api_quality and buildable_today from these. [MCP SEARCH RESULT] \
sections are only evidence about whether an MCP server exists; never conclude a product has \
no API merely because an MCP page doesn't describe one.

Rules:
- auth_methods: list every authentication method the text explicitly mentions \
(oauth2, api_key, basic_auth, custom_token, jwt). Use "none" only if the product \
explicitly has no auth. Use "unknown" if the text doesn't say.
- access_model: "free_signup" if anyone can sign up and get API access immediately for free; \
"freemium" if there's a free tier with API access plus paid tiers; \
"paid_plan_required" if API access requires a paid plan; \
"sales_contact_required" if you must talk to sales/apply for access; \
"invite_only" if access is by invitation/beta only; "unknown" if unclear.
- self_serve: true only if a developer can get real API credentials themselves, today, for \
free or on a trial, with no sales call, admin approval, or partnership required. false if \
it's gated behind payment, sales contact, admin/partner approval, or invite.
- api_quality: "rich_rest" for a broad, well-documented REST API; "limited_rest" for a \
narrow/basic REST API; "graphql" if primarily GraphQL; "soap_legacy" for SOAP/XML-RPC only; \
"no_public_api" if there is no public API; "unknown" if unclear.
- has_mcp: true only if the given text explicitly mentions an existing MCP (Model Context \
Protocol) server for this app (official or well-known third-party). false otherwise — do not \
guess or infer one exists just because the API looks agent-friendly.
- mcp_notes: if has_mcp is true, name/link the MCP found. If false, leave brief or empty.
- buildable_today: "yes_easy" if a self-serve API key/OAuth app can be created today with \
good docs; "yes_hard" if possible but requires approval, partnership, or has poor docs; \
"no_blocked" if there's no way to get programmatic access today.
- blockers: short phrases naming anything that would block building a connector today \
(e.g. "requires partner approval", "no public API", "enterprise sales only").
- confidence: your own confidence (0.0-1.0) in this extraction given the text quality.
- source_url: the single most authoritative URL from the provided sources for this data.
- notes: anything surprising or ambiguous worth a human double-checking.

Return ONLY valid JSON matching the given schema. No prose outside the JSON.
"""

def extraction_user_prompt(app_name: str, category: str, urls: list[str], content: str) -> str:
    url_list = "\n".join(f"- {u}" for u in urls)
    return f"""App: {app_name}
Category: {category}

Source URLs:
{url_list}

Scraped content:
{content[:6500]}
"""

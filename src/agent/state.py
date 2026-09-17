"""Pydantic schema for a single app's research result + LangGraph agent state."""
from __future__ import annotations

from typing import Literal, Optional, TypedDict

from pydantic import BaseModel, Field

AuthMethod = Literal[
    "oauth2", "api_key", "basic_auth", "custom_token", "jwt", "none", "unknown"
]

AccessModel = Literal[
    "free_signup", "freemium", "paid_plan_required",
    "sales_contact_required", "invite_only", "unknown",
]

ApiQuality = Literal[
    "rich_rest", "limited_rest", "graphql", "soap_legacy",
    "no_public_api", "unknown",
]

Buildable = Literal["yes_easy", "yes_hard", "no_blocked"]


class AppResearch(BaseModel):
    app_name: str
    category: str
    description: str = Field(description="One sentence: what the app does")
    auth_methods: list[AuthMethod] = Field(default_factory=list)
    access_model: AccessModel = "unknown"
    self_serve: bool = Field(default=False, description="True if a developer can get credentials themselves for free/trial, without sales/admin approval")
    api_quality: ApiQuality = "unknown"
    has_mcp: bool = Field(default=False, description="True if the app already has a known/published MCP server")
    mcp_notes: str = Field(default="", description="Where the existing MCP was found, or why none was found")
    buildable_today: Buildable = "no_blocked"
    blockers: list[str] = Field(default_factory=list)
    source_url: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: str = ""


class AgentState(TypedDict, total=False):
    app_name: str
    category: str
    query: str
    search_results: list[dict]
    mcp_results: list[dict]
    scraped_content: str
    scraped_urls: list[str]
    extraction: Optional[AppResearch]
    retry_count: int
    error: Optional[str]

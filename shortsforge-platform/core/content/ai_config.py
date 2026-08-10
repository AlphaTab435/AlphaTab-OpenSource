"""
Configuration for AI Providers, Models, and Free-Tier tracking.
This file acts as the source of truth for the Fallback Chain hierarchy and available models.
"""

# The order of keys in FALLBACK_CHAIN dictates the automatic routing order
# if the PRIMARY_AI_PROVIDER fails with a 429 Rate Limit error.
FALLBACK_CHAIN = ["groq", "cerebras", "gemini"]

# Comprehensive configuration for all supported AI text generation providers.
# - 'api_base': The OpenAI-compatible base URL (if applicable).
# - 'models': List of available models.
#   - 'id': The literal string sent to the API.
#   - 'label': A human-readable quality/speed indicator for the UI.
#   - 'tier_info': Developer notes on the current free-tier limits.
AI_PROVIDERS = {
    "cerebras": {
        "api_base": "https://api.cerebras.ai/v1",
        "models": [
            {
                "id": "zai-glm-4.7",
                "label": "High Quality (GLM)",
                "tier_info": "1,000,000 tokens/day; 2,400 req/day"
            },
            {
                "id": "gpt-oss-120b",
                "label": "Budget / Blazing Fast",
                "tier_info": "1,000,000 tokens/day; 2,400 req/day"
            }
        ],
        "default_model": "zai-glm-4.7"
    },
    "groq": {
        "api_base": "https://api.groq.com/openai/v1",
        "models": [
            {
                "id": "openai/gpt-oss-120b",
                "label": "Top Quality / Fast",
                "tier_info": "1,000 req/day; 200,000 tokens/day (Dev Tier)"
            }
        ],
        "default_model": "openai/gpt-oss-120b"
    },
    "gemini": {
        "api_base": None, # Uses google-generativeai pip package securely
        "models": [
            {
                "id": "gemini-3.1-flash-lite",
                "label": "High Volume / Fast",
                "tier_info": "500 req/day (Free Tier)"
            },
            {
                "id": "gemini-2.5-flash",
                "label": "High Quality / Fast",
                "tier_info": "20 req/day (Free Tier)"
            }
        ],
        "default_model": "gemini-3.1-flash-lite"
    }
}

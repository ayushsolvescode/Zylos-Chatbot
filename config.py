"""Configuration constants for the ZYLOS chat app.

Keep the user-facing defaults and session protection thresholds here so the
main application logic in app.py remains easy to read and adjust.
"""

# Default system prompt sent to the chat API as the initial system message.
DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."

# Default available models and the model selected by default in the UI.
AVAILABLE_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-3o-mini"]
DEFAULT_MODEL = "gpt-4o-mini"

# Protect against accidental overuse of a free OpenRouter quota by limiting how
# many user messages can be sent in a single browser session.
DEFAULT_SESSION_MESSAGE_LIMIT = 20
MAX_SESSION_MESSAGE_LIMIT = 100

# OpenRouter API configuration values.
OPENROUTER_API_ENDPOINT = "https://api.openrouter.ai/v1/chat/completions"
OPENROUTER_API_KEY_ENV_VAR = "OPENROUTER_API_KEY"
OPENROUTER_API_REQUEST_TIMEOUT = 60

# Document context settings for uploaded files. Documents are chunked and only
# the most relevant chunks are sent to the API when total content is too large.
DOCUMENT_CONTEXT_MAX_CHARS = 4000
DOCUMENT_CHUNK_SIZE = 1200
DOCUMENT_CHUNK_OVERLAP = 200

# When the conversation history grows beyond this many messages, summarize older
# messages to keep request payloads smaller while preserving long-term context.
SUMMARY_TRIGGER_COUNT = 10

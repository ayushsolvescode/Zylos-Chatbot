import base64
import json
import os

import requests
import streamlit as st
from dotenv import load_dotenv
import docx
import pypdf

from config import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    DEFAULT_SESSION_MESSAGE_LIMIT,
    MAX_SESSION_MESSAGE_LIMIT,
    DEFAULT_SYSTEM_PROMPT,
    OPENROUTER_API_ENDPOINT,
    OPENROUTER_API_KEY_ENV_VAR,
    OPENROUTER_API_REQUEST_TIMEOUT,
    DOCUMENT_CONTEXT_MAX_CHARS,
    DOCUMENT_CHUNK_OVERLAP,
    DOCUMENT_CHUNK_SIZE,
    SUMMARY_TRIGGER_COUNT,
)


class OpenRouterAPIError(Exception):
    """Base class for OpenRouter API errors."""


class RateLimitError(OpenRouterAPIError):
    """Raised when the API returns HTTP 429."""


class InvalidAPIKeyError(OpenRouterAPIError):
    """Raised when the API returns HTTP 401 invalid credentials."""


# Load the API key from .env so it does not live in source control.
load_dotenv()
# Prefer the Streamlit secrets manager when deployed on Streamlit Community Cloud.
# `st.secrets` is secure and not stored in the repo. Locally we fall back to `.env`.
OPENROUTER_API_KEY = None
try:
    OPENROUTER_API_KEY = st.secrets.get(OPENROUTER_API_KEY_ENV_VAR)
except Exception:
    # If Streamlit secrets are not available (e.g., running outside Streamlit), ignore.
    OPENROUTER_API_KEY = None

if not OPENROUTER_API_KEY:
    OPENROUTER_API_KEY = os.getenv(OPENROUTER_API_KEY_ENV_VAR, "")

# File upload helpers for .txt, .pdf, and .docx documents.
# Uploaded text is stored in session_state so it can be reused later in the
# session without re-parsing the file on every rerun.
def extract_text_from_txt(uploaded_file) -> str:
    raw_bytes = uploaded_file.getvalue()
    return raw_bytes.decode("utf-8", errors="replace")


def extract_text_from_pdf(uploaded_file) -> str:
    reader = pypdf.PdfReader(uploaded_file)
    extracted_pages = []
    for page in reader.pages:
        extracted_pages.append(page.extract_text() or "")
    return "\n\n".join(extracted_pages).strip()


def extract_text_from_docx(uploaded_file) -> str:
    document = docx.Document(uploaded_file)
    return "\n\n".join(paragraph.text for paragraph in document.paragraphs).strip()


def extract_file_text(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    filename = uploaded_file.name.lower()
    if filename.endswith(".txt"):
        return extract_text_from_txt(uploaded_file)
    if filename.endswith(".pdf"):
        return extract_text_from_pdf(uploaded_file)
    if filename.endswith(".docx"):
        return extract_text_from_docx(uploaded_file)

    return ""


def chunk_document_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split long documents into overlapping chunks for relevance matching."""
    if not text:
        return []

    chunks = []
    start = 0
    text_length = len(text)
    while start < text_length:
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap
    return [chunk for chunk in chunks if chunk]


def select_relevant_document_chunks(query: str, documents: dict[str, str], max_chunks: int = 3, prioritized_doc: str = None) -> list[tuple[str, str, int]]:
    """Select the most relevant document chunks for a query using keyword matches.
    
    Returns chunks with their relevance scores. If a document is prioritized,
    its chunks receive a boost to their scores to encourage selection.
    """
    query_terms = [term.lower() for term in query.split() if len(term) > 3]
    if not query_terms:
        return []

    scored_chunks = []
    for filename, text in documents.items():
        chunks = chunk_document_text(text, DOCUMENT_CHUNK_SIZE, DOCUMENT_CHUNK_OVERLAP)
        for chunk in chunks:
            score = sum(chunk.lower().count(term) for term in query_terms)
            # Boost the score if this chunk is from the prioritized document.
            if prioritized_doc and filename == prioritized_doc:
                score = score * 1.5 + 5
            if score > 0:
                scored_chunks.append((score, filename, chunk))

    scored_chunks.sort(reverse=True, key=lambda item: item[0])
    selected = []
    for score, filename, chunk in scored_chunks[:max_chunks]:
        selected.append((filename, chunk, int(score)))
    return selected


def prepare_document_context(uploaded_text: str, max_length: int = DOCUMENT_CONTEXT_MAX_CHARS) -> str:
    """Prepare uploaded document text for inclusion in API requests.

    If the document is very long, truncate it to avoid bloating the API request
    and consuming unnecessary tokens. This lets the assistant answer questions
    about the document while keeping the request payload manageable.

    Args:
        uploaded_text: The full extracted text from the uploaded document.
        max_length: Maximum characters to include. Defaults to 4000.

    Returns:
        The truncated document text, or an empty string if no text is present.
    """
    if not uploaded_text:
        return ""
    if len(uploaded_text) <= max_length:
        return uploaded_text
    # If the document is longer than max_length, truncate and add an ellipsis.
    truncated = uploaded_text[:max_length].rstrip()
    return truncated + "\n\n[... document truncated due to length ...]"


# Helper to load the background image, encode it in base64, and inject it into CSS.
# Streamlit does not natively support full-page background images, so we use a
# data URI and custom CSS to set the body background.
def get_base64_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

background_image = get_base64_image("assets/background.webp")

st.markdown(
    f"""
    <style>
    body {{
        background-image: url("data:image/webp;base64,{background_image}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    div[data-testid="stAppViewContainer"] > .main {{
        background: rgba(15, 23, 42, 0.68) !important;
        border-radius: 24px;
        padding: 1.5rem;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
    }}
    div[data-testid="stSidebar"] {{
        background: rgba(12, 20, 50, 0.80) !important;
        color: #f8fafc;
    }}
    div[data-testid="stSidebar"] label,
    div[data-testid="stSidebar"] h2,
    div[data-testid="stSidebar"] p {{
        color: #f8fafc !important;
    }}
    .stChatMessage {{
        background: rgba(255, 255, 255, 0.88) !important;
        border-radius: 18px !important;
        padding: 1rem !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div style='background: linear-gradient(135deg, rgba(14, 60, 125, 0.2) 0%, rgba(255, 255, 255, 0.15) 100%); padding: 24px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.4); backdrop-filter: blur(10px);'>
        <h1 style='margin: 0; font-size: 2.5rem; color: #f8fafc;'>ZYLOS</h1>
        <p style='margin: 12px 0 0; font-size: 1.05rem; color: #e2e8f0;'>
            A polished Streamlit chatbot interface with streaming OpenRouter responses, model selection, and custom system prompts.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

st.info("Type your message below and press Enter. Responses stream live as the assistant generates them.")

st.markdown("---")

if st.session_state.uploaded_documents:
    st.info(f"{len(st.session_state.uploaded_documents)} document(s) loaded into context")

# Sidebar controls for prompt editing, model selection, and conversation reset.
with st.sidebar:
    st.header("Settings")
    system_prompt = st.text_area(
        "System prompt",
        value=DEFAULT_SYSTEM_PROMPT,
        help="This system prompt is sent to the API as the first message with role=system.",
        height=150,
    )

    selected_model = st.selectbox(
        "Model",
        options=AVAILABLE_MODELS,
        index=AVAILABLE_MODELS.index(DEFAULT_MODEL),
        help="Choose a free OpenRouter model. The selected model is sent in the request payload.",
    )

    uploaded_files = st.file_uploader(
        "Upload documents",
        type=["txt", "pdf", "docx"],
        accept_multiple_files=True,
        help="Upload text, PDF, or Word documents. Extracted text is stored per file in session state.",
    )
    if uploaded_files is not None and len(uploaded_files) > 0:
        for uploaded_file in uploaded_files:
            extracted_text = extract_file_text(uploaded_file)
            st.session_state.uploaded_documents[uploaded_file.name] = extracted_text
        st.success(
            f"Uploaded {len(uploaded_files)} document(s) successfully."
        )

    if st.session_state.uploaded_documents:
        st.markdown("**Documents loaded:**")
        for filename, document_text in st.session_state.uploaded_documents.items():
            preview_text = document_text[:260].replace("\n", " ")
            st.write(f"• **{filename}** — {len(document_text)} characters")
            if preview_text:
                st.code(preview_text + ("..." if len(document_text) > 260 else ""))
        
        # Allow the user to prioritize one document for better chunk selection.
        # This boosts relevance scores for chunks from the prioritized document.
        prioritize_options = ["None"] + list(st.session_state.uploaded_documents.keys())
        st.session_state.prioritized_document = st.selectbox(
            "Prioritize document (for chunk selection)",
            options=prioritize_options,
            help="Boost relevance scores for chunks from this document during query matching.",
        )
        
        if st.button("Clear uploaded documents"):
            # Clearing uploaded_documents removes all document context from
            # session_state, so uploaded files are no longer considered in API requests.
            st.session_state.uploaded_documents = {}
            st.session_state.prioritized_document = "None"
            st.success("All uploaded documents cleared from context.")

    session_message_limit = st.number_input(
        "Session message limit",
        min_value=1,
        max_value=MAX_SESSION_MESSAGE_LIMIT,
        value=DEFAULT_SESSION_MESSAGE_LIMIT,
        help="Stop the session after a fixed number of user messages to avoid accidental free quota overuse.",
    )

    st.caption(
        f"Session usage: {st.session_state.get('message_count', 0)} / {session_message_limit} messages"
    )

    if st.button("Clear conversation"):
        # Reset conversation state so the chat bubbles disappear.
        st.session_state.messages = []
        st.session_state.summary = ""
        st.session_state.message_count = 0
        st.session_state.uploaded_documents = {}
        st.experimental_rerun()

# Initialize the conversation history in session_state on first run.
if "messages" not in st.session_state:
    st.session_state.messages = []
if "summary" not in st.session_state:
    st.session_state.summary = ""
if "message_count" not in st.session_state:
    # Track how many messages the user has sent in this browser session.
    # This protects against accidental overuse of the free OpenRouter quota by
    # stopping requests once the session reaches a safe default limit.
    st.session_state.message_count = 0
if "uploaded_documents" not in st.session_state:
    st.session_state.uploaded_documents = {}
if "prioritized_document" not in st.session_state:
    st.session_state.prioritized_document = "None"


def stream_openrouter(messages: list, model: str):
    """Stream the OpenRouter assistant response chunk by chunk."""
    endpoint = OPENROUTER_API_ENDPOINT
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 200,
        "stream": True,
    }

    try:
        with requests.post(endpoint, headers=headers, json=payload, stream=True, timeout=OPENROUTER_API_REQUEST_TIMEOUT) as response:
            # Handle invalid API key (401) with a friendly error.
            if response.status_code == 401:
                raise InvalidAPIKeyError(
                    "Invalid API key. Please update your OPENROUTER_API_KEY in Streamlit Secrets or .env."
                )
            # Handle rate limiting specifically so the user can retry later.
            if response.status_code == 429:
                raise RateLimitError(
                    "Rate limit reached. Please wait a moment and try again."
                )
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    message = error_data.get("error", {}).get("message") or str(error_data)
                except ValueError:
                    message = response.text
                raise OpenRouterAPIError(
                    f"OpenRouter API error ({response.status_code}): {message}"
                )

            # OpenRouter streams data as newline-delimited JSON.
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue

                line = raw_line.strip()
                if line.startswith("data:"):
                    line = line[len("data:"):].strip()

                if line == "[DONE]":
                    break

                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue

                choices = chunk.get("choices", [])
                if not choices:
                    continue

                delta = choices[0].get("delta", {})
                # Some stream responses use `delta.content`.
                content = delta.get("content")
                if content:
                    yield content
                    continue

                # Other responses may package the full message.
                message_body = choices[0].get("message", {})
                if message_body:
                    content = message_body.get("content")
                    if content:
                        yield content
    except requests.exceptions.Timeout:
        raise OpenRouterAPIError("The request timed out. Please try again.")
    except requests.exceptions.ConnectionError:
        raise OpenRouterAPIError(
            "Network connection error. Please check your internet and try again."
        )
    except requests.exceptions.RequestException as e:
        raise OpenRouterAPIError(f"Request error: {e}")


def summarize_old_history(messages, current_summary, model, system_prompt):
    """Summarize earlier conversation history to keep memory compact."""
    # We keep a separate running summary in session_state so the display history
    # remains full, but the model only receives compressed earlier context.
    # This is more efficient than sending the full message history every time.
    # Select older messages to summarize, excluding the most recent entries.
    old_messages = messages[:-6]
    if not old_messages:
        return current_summary

    # Build a single summary prompt for the assistant.
    prompt = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Please summarize the following conversation concisely, "
                "including the main points and any user preferences. "
                "Keep it short and in plain language."
            ),
        },
    ]
    # Convert the old messages to a compact text format so the model can summarize them.
    prompt.append({"role": "user", "content": json.dumps(old_messages)})

    # If we already have a running summary, ask the model to combine it.
    if current_summary:
        prompt.append(
            {
                "role": "user",
                "content": (
                    "Also combine this with the previous summary: "
                    + current_summary
                ),
            }
        )

    endpoint = OPENROUTER_API_ENDPOINT
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": prompt,
        "max_tokens": 150,
        "stream": False,
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=OPENROUTER_API_REQUEST_TIMEOUT)
        if response.status_code == 401:
            raise InvalidAPIKeyError(
                "Invalid API key. Please update your OPENROUTER_API_KEY in Streamlit Secrets or .env."
            )
        if response.status_code == 429:
            raise RateLimitError(
                "Rate limit reached while summarizing. Please wait and try again."
            )
        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("error", {}).get("message") or str(error_data)
            except ValueError:
                message = response.text
            raise OpenRouterAPIError(
                f"OpenRouter API error ({response.status_code}): {message}"
            )

        data = response.json()
    except requests.exceptions.Timeout:
        raise OpenRouterAPIError("Summary request timed out. Please try again.")
    except requests.exceptions.ConnectionError:
        raise OpenRouterAPIError(
            "Network connection error while summarizing. Please check your connection."
        )
    except requests.exceptions.RequestException as e:
        raise OpenRouterAPIError(f"Summary request error: {e}")

    choices = data.get("choices", [])
    if not choices:
        return current_summary

    first_choice = choices[0]
    message_body = first_choice.get("message", {})
    summary_text = message_body.get("content", "")
    # Keep the running summary concise and return it.
    return summary_text.strip()


# Display the full conversation using chat bubbles.
with st.container():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


# st.chat_input creates a chat-style input box with enter-to-send behavior.
user_text = st.chat_input("Type a message...", key="chat_input")

session_limit_reached = st.session_state.message_count >= session_message_limit
if session_limit_reached:
    st.warning(
        "Session limit reached. Please refresh the page or wait before continuing to avoid accidental overuse of the free API quota."
    )

if user_text is not None:
    if session_limit_reached:
        # Do not allow a new API request once the session limit is reached.
        st.warning(
            "You have reached the maximum number of messages for this session. "
            "Refresh the page to start a new session."
        )
    elif not user_text.strip():
        # Handle empty input so blank messages are not sent.
        st.warning("Please type a message before sending.")
    elif not OPENROUTER_API_KEY or "your_openrouter_api_key" in OPENROUTER_API_KEY:
        # Inform the user if the API key is missing or still a placeholder.
        st.error("Please add a valid OPENROUTER_API_KEY to .env before sending messages.")
    else:
        # Append the user's message so the chat bubble history updates immediately.
        st.session_state.messages.append({"role": "user", "content": user_text})
        st.session_state.message_count += 1

        try:
            with st.chat_message("assistant"):
                # Before sending a new message, summarize old history if the
                # conversation is long. This keeps the request payload smaller
                # while preserving relevant earlier context.
                if len(st.session_state.messages) > SUMMARY_TRIGGER_COUNT:
                    st.session_state.summary = summarize_old_history(
                        st.session_state.messages,
                        st.session_state.summary,
                        selected_model,
                        system_prompt,
                    )

                recent_messages = st.session_state.messages[-6:]
                # Build the API message list. Start with the user-provided system prompt,
                # then add optional context about previous conversation (summary),
                # then add the uploaded document context if one exists,
                # and finally add the recent user/assistant messages.
                api_messages = [{"role": "system", "content": system_prompt}]
                
                # Include a summary of earlier messages to preserve long-term context
                # without sending the full message history every time.
                if st.session_state.summary:
                    api_messages.append(
                        {
                            "role": "system",
                            "content": (
                                "Summary of previous conversation: "
                                + st.session_state.summary
                            ),
                        }
                    )
                
                # If the user has uploaded documents, include the most relevant
                # chunks from those documents as system context for the assistant.
                # This basic relevance selection uses simple keyword matching to
                # choose the most likely chunks to answer the user's query.
                # Chunks are scored by keyword frequency, with a boost if from a prioritized document.
                if st.session_state.uploaded_documents:
                    prioritized = None if st.session_state.prioritized_document == "None" else st.session_state.prioritized_document
                    relevant_chunks = select_relevant_document_chunks(
                        user_text,
                        st.session_state.uploaded_documents,
                        max_chunks=4,
                        prioritized_doc=prioritized,
                    )
                    if relevant_chunks:
                        api_messages.append(
                            {
                                "role": "system",
                                "content": (
                                    "Relevant document excerpts (by relevance score):\n\n"
                                    + "\n\n".join(
                                        f"[{filename}, score: {score}]\n{chunk}"
                                        for filename, chunk, score in relevant_chunks
                                    )
                                ),
                            }
                        )
                    else:
                        # If no relevant chunks are found, fall back to a shorter
                        # summary of the full uploaded documents.
                        uploaded_combined = "\n\n".join(
                            f"{name}: {prepare_document_context(text)}"
                            for name, text in st.session_state.uploaded_documents.items()
                        )
                        api_messages.append(
                            {
                                "role": "system",
                                "content": (
                                    "Uploaded documents content (truncated due to length):\n\n"
                                    + uploaded_combined
                                ),
                            }
                        )
                
                # Only send the most recent messages for display context.
                # The running summary provides older conversation memory without
                # bloating the request with every prior chat message.
                api_messages.extend(recent_messages)

                # st.write_stream accepts an iterator and renders text as it arrives.
                
                # Display which document chunks are being used in an expander.
                if st.session_state.uploaded_documents and relevant_chunks:
                    with st.expander("📄 Document chunks being used"):
                        for filename, chunk, score in relevant_chunks:
                            st.write(f"**{filename}** (relevance score: {score})")
                            st.code(chunk[:300] + ("..." if len(chunk) > 300 else ""), language="plaintext")
                
                response_generator = stream_openrouter(api_messages, selected_model)
                assistant_content = ""
                placeholder = st.empty()

                for chunk in response_generator:
                    assistant_content += chunk
                    placeholder.write_stream([chunk])

            # After streaming completes, save the full assistant text.
            st.session_state.messages.append({"role": "assistant", "content": assistant_content})
            st.experimental_rerun()
        except InvalidAPIKeyError as e:
            # Invalid key means the credentials are wrong or expired.
            st.error(str(e))
            if st.button("Retry"):
                st.experimental_rerun()
        except RateLimitError as e:
            # Rate limit errors are temporary and can usually be retried.
            st.error(str(e))
            if st.button("Retry"):
                st.experimental_rerun()
        except OpenRouterAPIError as e:
            # User-facing message for any other API issue.
            st.error(str(e))
            if st.button("Retry"):
                st.experimental_rerun()
        except Exception as e:
            # Fallback for unexpected errors.
            st.error("An unexpected error occurred. Please try again later.")
            if st.button("Retry"):
                st.experimental_rerun()

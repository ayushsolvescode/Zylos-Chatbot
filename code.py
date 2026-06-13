import os
import streamlit as st

try:
    import google.generativeai as genai
except ModuleNotFoundError:
    st.error(
        "Missing package: google-generativeai. Install it with:\n"
        "pip install google-generativeai streamlit"
    )
    raise

APP_TITLE = "SmartBot - Your AI Chatbot"
MODEL_NAME = "gemini-3.5-flash"


def load_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key.strip()

    api_key_path = os.path.join(os.path.dirname(__file__), "gemini_api_key.txt")
    if os.path.exists(api_key_path):
        with open(api_key_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    raise FileNotFoundError(
        "Gemini API key not found. Set GEMINI_API_KEY or create gemini_api_key.txt."
    )


def get_assistant_response(messages):
    """Generate a chatbot response using Gemini."""
    try:
        response = genai.ChatCompletion.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
        )
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message"):
                return choice.message.get("content", "")
            if isinstance(choice, dict) and "message" in choice:
                return choice["message"].get("content", "")
    except AttributeError:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = "\n".join(
            f"{msg['role'].capitalize()}: {msg['content']}" for msg in messages
        )
        prompt += "\nAssistant:"
        response = model.generate_text(prompt=prompt, temperature=0.7)
        if hasattr(response, "text"):
            return response.text
        return str(response)

    if hasattr(response, "last"):
        return getattr(response, "last")

    return str(response)


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="🤖")
    st.title(APP_TITLE)
    st.write("Ask me anything!")

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "system", "content": "You are a helpful AI assistant."}
        ]

    if "api_key_loaded" not in st.session_state:
        try:
            genai.configure(api_key=load_api_key())
            st.session_state.api_key_loaded = True
        except Exception as exc:
            st.error(str(exc))
            return

    def send_message():
        user_input = st.session_state.user_input.strip()
        if not user_input:
            return

        st.session_state.messages.append({"role": "user", "content": user_input})
        assistant_text = get_assistant_response(st.session_state.messages)
        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
        st.session_state.user_input = ""

    st.text_input(
        "You:",
        key="user_input",
        on_change=send_message,
        placeholder="Type your message and press Enter",
    )

    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f"**You:** {message['content']}")
        elif message["role"] == "assistant":
            st.markdown(f"**SmartBot:** {message['content']}")


if __name__ == "__main__":
    main()
    

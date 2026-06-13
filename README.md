# Streamlit AI Chatbot (OpenRouter)

This project is a minimal starting point for a Streamlit-based chatbot that will use the OpenRouter API.

Files:
- `app.py` — Minimal Streamlit UI (title and single text input) used to test rerun behavior.
- `main.py` and `code.py` — workspace files (not modified by this setup).
- `requirements.txt` — lists Python dependencies; include comments describing each dependency.
- `.env` — stores sensitive configuration like `OPENROUTER_API_KEY`. This file is ignored by Git for security.
- `.gitignore` — tells Git which files/folders to ignore (virtual envs, `.env`, bytecode, IDE folders).
- `.venv/` or `venv/` — local Python virtual environment folder (not committed).

Setup and run (Windows PowerShell):

```powershell
# Create virtual environment (if you don't have one already)
C:/Users/ayush/AppData/Local/Programs/Python/Python314/python.exe -m venv .venv

# Activate
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run the Streamlit app
streamlit run app.py
```

Security note:
- Do not commit `.env` or any real API keys to version control.
- Replace the placeholder in `.env` with your real `OPENROUTER_API_KEY` locally.

Deployment to Streamlit Community Cloud
--------------------------------------

1. Ensure `requirements.txt` lists all dependencies (see file in this repo).

2. Keep `.env` in `.gitignore` (do not push it). Instead, use Streamlit's Secrets manager:
	- On share.streamlit.io, after creating your app, open the app's "Settings" → "Secrets" panel.
	- Add a key named `OPENROUTER_API_KEY` with your API key as the value.
	- In the app code we prefer `st.secrets.get("OPENROUTER_API_KEY")` and fall back to `.env` locally.

3. Push your project to GitHub:
	- Initialize the repo (if not already):

```bash
git init
git add .
git commit -m "Initial commit: Streamlit OpenRouter chatbot"
```

	- Create a new GitHub repository (via the website or `gh repo create`) and push:

```bash
git remote add origin https://github.com/<your-username>/<your-repo>.git
git branch -M main
git push -u origin main
```

4. Deploy on Streamlit Community Cloud:
	- Go to https://share.streamlit.io and sign in with GitHub.
	- Click "New app", select your repository, branch (`main`) and the file path to `app.py`.
	- Click "Deploy". After a few moments the app will be live at a shareable URL.

Notes:
- Do NOT add your `.env` or `secrets.toml` to the repository. Use the Streamlit Secrets UI for production secrets.
- If you need to test secrets locally, create a `.streamlit/secrets.toml` (do not commit it):

```toml
OPENROUTER_API_KEY = "sk-..."
```

That's it — once deployed your app will read `OPENROUTER_API_KEY` from `st.secrets` and the streaming chat will work on the public URL.

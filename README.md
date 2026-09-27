# Chapter Chalk — AI School Tutor (web version)

This turns your original CLI script into a small Flask website. The Gemini
API key now lives on the server, in a `.env` file that git never sees —
the browser never gets a copy of it.

## Files

```
webapp/
├── app.py              # Flask backend — the only place that touches the API key
├── requirements.txt    # Python dependencies
├── .env.example        # Template — copy this to .env
├── .gitignore          # Tells git to skip .env and other junk
├── templates/
│   └── index.html      # The page
└── static/
    ├── style.css
    └── script.js        # Talks to /api/start and /api/chat
```

## 1. Install dependencies

```bash
cd webapp
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Add your real API key (this is the part that keeps it hidden)

```bash
cp .env.example .env
```

Open `.env` and fill in your real key:

```
GEMINI_API_KEY=AIza...your-real-key...
FLASK_SECRET_KEY=any-long-random-string
```

**Why this keeps the key safe:** `app.py` loads the key from `.env` at
runtime with `load_dotenv()` — the key itself is never typed into any
`.py` file. The `.gitignore` file has this line:

```
.env
```

That tells git to never track `.env`, so even if you run `git add .`,
the file with your real key will not be staged or committed. Only
`.env.example` (which has a fake placeholder value) goes into git —
that's what teammates or your future self use as a template.

If you ever *do* commit a real key by accident: treat it as leaked —
revoke/regenerate the key in Google AI Studio immediately, since removing
it from a later commit doesn't erase it from git history.

## 3. Run it locally

```bash
python app.py
```

Visit `http://localhost:5000`.

## 4. Put it on GitHub

```bash
git init
git add .
git commit -m "Chapter Chalk web tutor"
git remote add origin <your-repo-url>
git push -u origin main
```

Because `.env` is git-ignored, `git status` will never list it, and it
won't appear on GitHub.

## 5. Deploying so others can use it

`.env` files are a local-dev convenience — hosting platforms don't read
them. When you deploy (e.g. Render, Railway, PythonAnywhere, Fly.io),
set the same two variables as **environment variables / secrets** in
that platform's dashboard instead of uploading `.env`:

- `GEMINI_API_KEY`
- `FLASK_SECRET_KEY`

The code doesn't change — `os.environ.get(...)` reads them the same way
whether they come from a local `.env` file or the host's secret manager.

## How it works

- `POST /api/start` — takes class/subject/chapter, fetches the matching
  chapter PDF from your GitHub repo, and starts a Gemini chat with that
  PDF as context. Returns a `chat_token`.
- `POST /api/chat` — takes `chat_token` + a message, forwards it to that
  chat session, and returns the tutor's reply.
- Chat sessions are kept in memory on the server (`ACTIVE_CHATS`), keyed
  by a random token stored in the browser's session cookie. That's fine
  for one person using it at a time; if you expect many students at once
  later, swap that dict for Redis or a database.

## Notes / things to double-check

- The original code used the model name `gemini-3.5-flash-lite` — kept
  as-is here since that's what you had; verify it's still a valid model
  name in the Gemini API before relying on this in production.
- There's no login system, so anyone with the URL can use it and spend
  your API quota. Fine for a personal/school project; add simple auth
  before sharing the link widely.

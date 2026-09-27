import os
import re
import uuid
import requests

from flask import Flask, request, jsonify, session, render_template
from dotenv import load_dotenv
from google import genai
from google.genai import types

# --- Load secrets from a local .env file (never committed to git) -----------
load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
    )

ai_client = genai.Client(api_key=GEMINI_API_KEY)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# Active tutor chats live in memory: {chat_token: genai chat object}
# Fine for a single small deployment; swap for a real store (redis, db) if you
# expect many students chatting at once.
ACTIVE_CHATS = {}


# --- Validation tables (same idea as the original CLI tool, just tidier) ----
def _class_aliases():
    words = {
        1: ("i", "one", "first", "1st"),
        2: ("ii", "two", "second", "2nd"),
        3: ("iii", "three", "third", "3rd"),
        4: ("iv", "four", "fourth", "4th"),
        5: ("v", "five", "fifth", "5th"),
        6: ("vi", "six", "sixth", "6th"),
        7: ("vii", "seven", "seventh", "7th"),
        8: ("viii", "eight", "eighth", "8th"),
        9: ("ix", "nine", "ninth", "9th"),
        10: ("x", "ten", "tenth", "10th"),
    }
    table = {}
    for n, (roman, word, ordinal_word, ordinal_num) in words.items():
        table[n] = [
            str(n), f"class-{n}", f"class{n}", f"class {n}",
            roman, f"class {roman}", f"class-{roman}",
            word, ordinal_word, ordinal_num,
        ]
    return table


CLASS_ALIASES = _class_aliases()

SUBJECT_ALIASES = {
    "Science": ["science", "sci", "general science"],
    "Maths": ["maths", "math", "mathematics", "geometry", "algebra"],
    "English": ["english", "eng", "english literature", "english grammar"],
    "Social-science": [
        "social science", "sst", "history", "geography", "civics", "social studies",
    ],
}

CHAPTER_ALIASES = {
    i: [str(i), f"chapter-{i}", f"chapter{i}", f"chapter {i}", f"ch-{i}", f"ch{i}", f"ch {i}"]
    for i in range(1, 11)
}


def normalize_class(raw):
    raw = (raw or "").lower().strip()
    for num, aliases in CLASS_ALIASES.items():
        if raw in aliases:
            return f"Class-{num}"
    return None


def normalize_subject(raw):
    raw = (raw or "").lower().strip()
    for name, aliases in SUBJECT_ALIASES.items():
        if raw in aliases:
            return name
    return None


def normalize_chapter(raw):
    raw = (raw or "").lower().strip()
    for num, aliases in CHAPTER_ALIASES.items():
        if raw in aliases:
            return f"Chapter-{num}"
    return None


def markdown_bold_to_html(text):
    """Turn **bold** into <strong>, keep line breaks. Everything else is escaped
    upstream by the templating layer since we only ever insert this via
    textContent-safe JSON, not raw HTML injection on the server side."""
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    return text.replace("\n", "<br>")


# --- Routes -------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/start", methods=["POST"])
def start_session():
    data = request.get_json(force=True) or {}
    student_class = normalize_class(data.get("student_class"))
    subject = normalize_subject(data.get("subject"))
    chapter = normalize_chapter(data.get("chapter"))

    if not student_class:
        return jsonify({"error": "Class not recognized. Try something like 'Class-8' or '8'."}), 400
    if not subject:
        return jsonify({"error": "Subject not recognized. Try Science, Maths, English or Social-science."}), 400
    if not chapter:
        return jsonify({"error": "Chapter not recognized. Try something like 'Chapter-1' or '1'."}), 400

    pdf_url = (
        "https://raw.githubusercontent.com/nesar-labs/AI-creation/main/"
        f"{student_class}/{subject}/{chapter}.pdf"
    )
    try:
        pdf_response = requests.get(pdf_url, timeout=20)
    except requests.RequestException as e:
        return jsonify({"error": f"Could not reach the chapter library: {str(e)}"}), 502

    if pdf_response.status_code != 200:
        return jsonify({
            "error": "Could not find that chapter's PDF. Double-check Class, Subject and Chapter."
        }), 404

    try:
        pdf_attachment = types.Part.from_bytes(data=pdf_response.content, mime_type="application/pdf")
        system_instruction = (
            f"You are an expert school tutor for {student_class} {subject}. "
            f"You are discussing {chapter} with a student. Use the attached PDF to answer questions. "
            "Keep answers simple, encouraging, and clear for a school student. "
            "If they ask something not in the chapter, politely let them know."
        )
        chat = ai_client.chats.create(
            model="gemini-3.5-flash-lite",
            history=[
                types.Content(
                    role="user",
                    parts=[
                        pdf_attachment,
                        types.Part.from_text(
                            text="Hi tutor, please analyze this chapter file so I can ask you questions about it."
                        ),
                    ],
                )
            ],
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=1),
        )
    except Exception as e:
        return jsonify({"error": f"Could not start the tutor session: {str(e)}"}), 500

    token = str(uuid.uuid4())
    ACTIVE_CHATS[token] = chat
    session["chat_token"] = token

    return jsonify({
        "message": f"Tutor ready for {student_class} · {subject} · {chapter}.",
        "chat_token": token,
    })


@app.route("/api/chat", methods=["POST"])
def chat_message():
    data = request.get_json(force=True) or {}
    token = data.get("chat_token") or session.get("chat_token")
    user_msg = (data.get("message") or "").strip()

    if not token or token not in ACTIVE_CHATS:
        return jsonify({"error": "No active tutor session. Start a session first."}), 400
    if not user_msg:
        return jsonify({"error": "Message is empty."}), 400

    chat = ACTIVE_CHATS[token]
    try:
        response = chat.send_message(user_msg)
        return jsonify({"reply": markdown_bold_to_html(response.text)})
    except Exception as e:
        return jsonify({"error": f"Error talking to the tutor: {str(e)}"}), 500


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug, port=port)

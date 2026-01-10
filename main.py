# ----------------------------------------------------------
# Kikizakeshi (OCR + LLM) – Cloud Run Version
# - OCR (Google Vision) + LLM (OpenAI)
# - Locale-based language default
# - User can override language (e.g., "Answer in English")
# - If user says "Explain in English" AFTER an answer, translate the LAST answer
# - If image is NOT alcohol, respond cheerfully ("Oops, not alcohol 😄")
# - Do NOT mention allergens in outputs (internal extraction can exist, but output forbids it)
# ----------------------------------------------------------

import os
import re
import uuid
import time
import json
import traceback
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple
import logging
import requests

from fastapi import FastAPI, File, Form, UploadFile, Request, Body
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from google.cloud import vision


# ============================================================
# Logging
# ============================================================
logging.basicConfig(level=logging.INFO)

# ============================================================
# App
# ============================================================
app = FastAPI(title="Kikizakeshi (OCR + LLM)")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ============================================================
# ENV
# ============================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_TIMEOUT_SEC = float(os.getenv("OPENAI_TIMEOUT_SEC", "45"))

WELCOME_MESSAGE_EN = (
    "Welcome. Snap a barcode / label photo — or type a note. "
    "I’ll explain what it is and how to enjoy it."
)

FINAL_FOOTER = (
    "\n\nIf anything is unclear, feel free to type a note and ask me. "
    "You can also show this answer to a nearby staff member and ask for help."
)

# ============================================================
# Session store (in-memory)
# ============================================================
# NOTE: Cloud Run may scale/restart; in-memory sessions can disappear. That's expected.
SESSIONS: Dict[str, Dict[str, Any]] = {}


def get_session(session_id: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    if session_id and session_id in SESSIONS:
        return session_id, SESSIONS[session_id]

    new_id = str(uuid.uuid4())
    SESSIONS[new_id] = {
        "created_at": time.time(),
        "preferred_language": None,   # "en" / "ja" / "es" / ...
        "last_answer": None,          # last visible answer string
        "last_payload": None,         # last payload (debug/translation context)
    }
    return new_id, SESSIONS[new_id]


# ============================================================
# Data model
# ============================================================
@dataclass
class ExtractedInfo:
    alcohol_type: str = "unknown"
    abv: Optional[str] = None
    volume_ml: Optional[str] = None
    brand: Optional[str] = None
    maker: Optional[str] = None
    region: Optional[str] = None
    polishing_ratio: Optional[str] = None
    sake_terms: List[str] = field(default_factory=list)

    # internal only: do not mention in outputs
    allergen_mentions: List[str] = field(default_factory=list)

    raw_text_snippet: str = ""


# ============================================================
# Locale -> default language / cuisine
# ============================================================
def locale_to_default_language(locale: str) -> str:
    """
    Minimal mapping:
    - ja* => ja
    - en* => en
    - es* => es
    - fr* => fr
    - de* => de
    - it* => it
    - pt* => pt
    - zh* => zh
    - ko* => ko
    fallback: en
    """
    l = (locale or "").strip().lower().replace("_", "-")
    if l.startswith("ja"):
        return "ja"
    if l.startswith("en"):
        return "en"
    if l.startswith("es"):
        return "es"
    if l.startswith("fr"):
        return "fr"
    if l.startswith("de"):
        return "de"
    if l.startswith("it"):
        return "it"
    if l.startswith("pt"):
        return "pt"
    if l.startswith("zh"):
        return "zh"
    if l.startswith("ko"):
        return "ko"
    return "en"


def locale_to_cuisine(locale: str) -> str:
    """
    A lightweight "pairing cuisine" hint based on locale.
    This is intentionally simple.
    """
    l = (locale or "").strip().lower().replace("_", "-")
    if l.startswith("ja"):
        return "Japanese"
    if l.startswith("en-us") or l.startswith("en-ca"):
        return "American"
    if l.startswith("en-gb"):
        return "British"
    if l.startswith("es"):
        return "Spanish/Latin"
    if l.startswith("fr"):
        return "French"
    if l.startswith("de"):
        return "German"
    if l.startswith("it"):
        return "Italian"
    if l.startswith("pt-br"):
        return "Brazilian"
    if l.startswith("pt"):
        return "Portuguese"
    if l.startswith("zh"):
        return "Chinese"
    if l.startswith("ko"):
        return "Korean"
    return "Local"


# ============================================================
# User intent detection (language override + translation request)
# ============================================================
_LANG_ALIASES = {
    "en": ["english", "in english", "answer in english", "explain in english", "英語", "英語で", "英訳"],
    "ja": ["japanese", "日本語", "日本語で"],
    "es": ["spanish", "español", "スペイン語", "スペイン語で"],
    "fr": ["french", "français", "フランス語", "フランス語で"],
    "de": ["german", "deutsch", "ドイツ語", "ドイツ語で"],
    "it": ["italian", "italiano", "イタリア語", "イタリア語で"],
    "pt": ["portuguese", "português", "ポルトガル語", "ポルトガル語で"],
    "zh": ["chinese", "中文", "中国語", "中国語で"],
    "ko": ["korean", "한국어", "韓国語", "韓国語で"],
}


def parse_language_preference(customer_text: str) -> Optional[str]:
    """
    Detect explicit language preference in the customer's text.
    Returns language code like "en" or None if not found.
    """
    t = (customer_text or "").strip().lower()
    if not t:
        return None

    # Strong patterns first
    for code, keys in _LANG_ALIASES.items():
        for k in keys:
            if k in t:
                return code

    # Simple "in xx" / "answer in xx" patterns (best-effort)
    m = re.search(r"\b(in|answer in|reply in|respond in)\s+([a-z]{2})\b", t)
    if m:
        return m.group(2)

    return None


def is_translate_request(customer_text: str) -> bool:
    """
    True if the user is likely asking to translate/convert the *previous answer*.
    """
    t = (customer_text or "").strip().lower()
    if not t:
        return False

    # English patterns commonly used by you
    if any(x in t for x in ["translate", "translation", "explain in english", "in english please"]):
        return True

    # Japanese patterns
    if any(x in t for x in ["英訳", "翻訳", "英語で説明", "英語でお願い", "訳して"]):
        return True

    return False


# ============================================================
# OCR
# ============================================================
def run_ocr(image_bytes: bytes) -> str:
    logging.info(f"OCR: start (bytes={len(image_bytes)})")
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)

    try:
        response = client.document_text_detection(image=image)
        if response.error.message:
            logging.error(f"Vision API error: {response.error.message}")
            raise RuntimeError(f"Vision API error: {response.error.message}")

        text = (response.full_text_annotation.text or "")
        logging.info(f"OCR: done (chars={len(text)}) snippet={text[:100]!r}")
        return text

    except Exception as e:
        logging.error(f"OCR failed: {e}")
        logging.error(traceback.format_exc())
        raise


def is_readable_enough(text: str) -> bool:
    t = text.strip()
    return len(t) >= 40 and sum(c.isalnum() for c in t) >= 15


# ============================================================
# Extraction (lightweight)
# ============================================================
ALCOHOL_TERMS = [
    "beer", "whiskey", "whisky", "vodka", "rum", "tequila", "gin",
    "wine", "brandy", "cognac", "sake", "shochu", "mead",
]

ALLERGEN_TOKENS = [
    ("wheat", ["小麦", "wheat"]),
    ("buckwheat", ["そば", "buckwheat"]),
    ("soy", ["大豆", "soy"]),
    ("milk", ["乳", "milk"]),
    ("egg", ["卵", "egg"]),
]


def extract_abv(text: str) -> Optional[str]:
    # best-effort, may be noisy
    m = re.search(r"(\d{1,2}(?:\.\d)?)\s*%?\s*(?:alc|abv|vol)?", text, re.IGNORECASE)
    return f"{m.group(1)}%" if m else None


def extract_volume_ml(text: str) -> Optional[str]:
    m = re.search(r"(\d{2,4})\s*(?:ml|mL)", text)
    return f"{m.group(1)}ml" if m else None


def extract_allergens(text: str) -> List[str]:
    # internal only: never surface in output
    found = []
    for name, toks in ALLERGEN_TOKENS:
        for tok in toks:
            if tok.lower() in text.lower():
                found.append(name)
                break
    return found


def extract_info(text: str) -> ExtractedInfo:
    alcohol_type = "unknown"
    lower = text.lower()
    for term in ALCOHOL_TERMS:
        if term in lower:
            alcohol_type = term
            break

    return ExtractedInfo(
        alcohol_type=alcohol_type,
        abv=extract_abv(text),
        volume_ml=extract_volume_ml(text),
        allergen_mentions=extract_allergens(text),
        raw_text_snippet=text[:320],
    )


def looks_like_alcohol(text: str) -> bool:
    t = (text or "").lower()
    # Alcohol-ish signals
    if any(k in t for k in ["abv", "alc", "alcohol", "proof", "%", "vol"]):
        return True
    if any(k in t for k in ["sake", "shochu", "whisky", "whiskey", "vodka", "gin", "rum", "tequila", "wine", "beer", "brandy", "cognac"]):
        return True
    return False


# ============================================================
# Prompts
# ============================================================
def system_prompt() -> str:
    """
    Main prompt. We force:
    - Use payload.target_language
    - If alcohol is unclear, ask for clearer photo/note
    - Always include pairing suggestions based on payload.cuisine
    - Do NOT mention allergens
    Output JSON only: {language, answer}
    """
    return (
        "You are a friendly liquor-store clerk.\n"
        "You will receive JSON payload with:\n"
        "- customer_text\n"
        "- locale\n"
        "- cuisine (pairing cuisine hint)\n"
        "- target_language\n"
        "- extracted (basic fields)\n"
        "- ocr_snippet\n\n"
        "RULES:\n"
        "1) Output JSON ONLY with keys: language, answer.\n"
        "2) language MUST equal payload.target_language.\n"
        "3) Answer must be specific to the label text when possible. If unclear, say what is missing.\n"
        "4) ALWAYS include 2-3 food pairing suggestions aligned to payload.cuisine.\n"
        "5) If the user asked for a specific language, follow it.\n"
        "6) Do NOT mention allergens, allergy, wheat/soy/milk/egg, or allergy warnings.\n"
        "7) Be concise but helpful.\n"
    )


def translation_system_prompt() -> str:
    """
    Translate ONLY the previous answer. No new facts.
    No allergen mentions.
    """
    return (
        "You are a translator.\n"
        "You will receive JSON payload with:\n"
        "- target_language\n"
        "- text\n\n"
        "RULES:\n"
        "1) Output JSON ONLY with keys: language, answer.\n"
        "2) Translate payload.text into payload.target_language.\n"
        "3) Preserve meaning; do not add new facts.\n"
        "4) Keep tone natural for a liquor-store customer.\n"
        "5) Do NOT mention allergens or allergy warnings.\n"
    )


def non_alcohol_system_prompt() -> str:
    """
    For non-alcohol items: cheerful, a bit playful.
    No allergens.
    """
    return (
        "You are a cheerful liquor-store clerk.\n"
        "The customer sent a photo but it does NOT look like an alcoholic beverage.\n"
        "Reply in payload.target_language with a light, friendly, humorous tone.\n"
        "Vibe example: 'Oops—this isn’t alcohol 😄' (friendly, not rude).\n"
        "Ask them to send a barcode/label photo of an alcohol product.\n"
        "Output JSON ONLY with keys: language, answer.\n"
        "Do NOT mention allergens or allergy warnings.\n"
    )


# ============================================================
# Output enforcement
# ============================================================
def _strip_allergen_words(s: str) -> str:
    """
    Last-line defense: remove obvious allergen words if model violates instruction.
    This is not perfect, but better than shipping allergy talk.
    """
    if not s:
        return s
    patterns = [
        r"\ballergen(s)?\b",
        r"\ballergy\b",
        r"\bwheat\b",
        r"\bsoy\b",
        r"\bmilk\b",
        r"\begg\b",
        r"\bbuckwheat\b",
        r"小麦",
        r"大豆",
        r"卵",
        r"乳",
        r"そば",
    ]
    out = s
    for p in patterns:
        out = re.sub(p, "", out, flags=re.IGNORECASE)
    # Clean double spaces
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


def enforce(llm_raw: Dict[str, Any], target_language: str) -> Dict[str, Any]:
    language = target_language or "en"
    answer = ""

    if isinstance(llm_raw, dict):
        answer = llm_raw.get("answer") or ""
        # Force language to target_language regardless of model output
        language = target_language or (llm_raw.get("language") or "en")

    answer = _strip_allergen_words(str(answer).strip())

    if not answer:
        answer = (
            "I couldn't generate a detailed response right now. "
            "Please retake the photo with better lighting, or type a short note (brand/product name)."
        )

    # Ensure footer (still no allergy talk inside footer)
    return {"language": language, "answer": (answer + FINAL_FOOTER)}


# ============================================================
# OpenAI client
# ============================================================
def call_llm(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing")

    url = f"{OPENAI_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }

    logging.info(f"LLM: calling model={OPENAI_MODEL} messages={len(messages)}")
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=OPENAI_TIMEOUT_SEC)
        r.raise_for_status()

        content = r.json()["choices"][0]["message"]["content"]
        llm_result = json.loads(content)

        logging.info(f"LLM: ok answer_snip={str(llm_result.get('answer',''))[:100]!r}")
        return llm_result

    except Exception as e:
        logging.error(f"LLM call failed: {e}")
        logging.error(traceback.format_exc())
        raise


# ============================================================
# Core analyze
# ============================================================
async def analyze_impl(
    customer_text: str,
    session_id: Optional[str],
    photos: List[UploadFile],
    client_locale: str,
):
    session_id, sess = get_session(session_id)

    customer_text = customer_text or ""
    client_locale = client_locale or ""

    # Detect explicit language preference and persist it
    explicit_lang = parse_language_preference(customer_text)
    if explicit_lang:
        sess["preferred_language"] = explicit_lang

    # Determine target language (explicit > session > locale default)
    target_language = sess.get("preferred_language") or locale_to_default_language(client_locale)
    cuisine = locale_to_cuisine(client_locale)

    translate_mode = is_translate_request(customer_text)

    logging.info(
        f"Analyze: session_id={session_id} photos={len(photos)} "
        f"locale={client_locale!r} target_lang={target_language!r} "
        f"explicit_lang={explicit_lang!r} translate_mode={translate_mode}"
    )

    # ------------------------------------------------------------------
    # Translation mode: if user requests translation AND no photos attached,
    # translate the LAST answer (no new OCR needed)
    # ------------------------------------------------------------------
    if translate_mode and (not photos or len(photos) == 0) and sess.get("last_answer"):
        src_text = str(sess["last_answer"])
        payload = {
            "target_language": target_language,
            "text": src_text,
        }
        try:
            llm_raw = call_llm(
                [
                    {"role": "system", "content": translation_system_prompt()},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ]
            )
            llm_out = enforce(llm_raw, target_language)
            sess["last_answer"] = llm_out["answer"]
            sess["last_payload"] = payload
            return {"status": "ok", "session_id": session_id, "llm": llm_out}
        except Exception:
            logging.error("Translation failed; falling back to a short message.")
            llm_out = enforce(
                {"answer": "Sorry — I couldn't translate that right now. Please try again."},
                target_language,
            )
            sess["last_answer"] = llm_out["answer"]
            sess["last_payload"] = payload
            return {"status": "ok", "session_id": session_id, "llm": llm_out}

    # ------------------------------------------------------------------
    # OCR flow (if photos exist)
    # ------------------------------------------------------------------
    ocr_texts: List[str] = []
    for p in photos or []:
        img = await p.read()
        try:
            logging.info(
                f"Photo: name={p.filename!r} content_type={p.content_type!r} bytes={len(img)}"
            )
            t = run_ocr(img)
            if is_readable_enough(t):
                ocr_texts.append(t)
            else:
                logging.warning(f"OCR not readable enough: file={p.filename!r} chars={len(t)}")
        except Exception:
            logging.error(f"OCR error: file={p.filename!r}")
            continue

    combined = "\n".join(ocr_texts)
    extracted = extract_info(combined) if combined else ExtractedInfo()

    # Non-alcohol check (cheerful response)
    is_alcohol = looks_like_alcohol(combined) or (extracted.alcohol_type != "unknown")

    if (photos and len(photos) > 0) and (not is_alcohol):
        joke_payload = {
            "target_language": target_language,
            "locale": client_locale,
            "cuisine": cuisine,
            "customer_text": customer_text,
            "ocr_snippet": combined[:300],
        }
        try:
            llm_raw = call_llm(
                [
                    {"role": "system", "content": non_alcohol_system_prompt()},
                    {"role": "user", "content": json.dumps(joke_payload, ensure_ascii=False)},
                ]
            )
            llm_out = enforce(llm_raw, target_language)
        except Exception:
            llm_out = enforce(
                {"answer": "Oops — this doesn’t look like alcohol 😄  Please send a barcode/label photo of an alcohol product."},
                target_language,
            )

        sess["last_answer"] = llm_out["answer"]
        sess["last_payload"] = joke_payload
        return {"status": "ok", "session_id": session_id, "llm": llm_out}

    # ------------------------------------------------------------------
    # Main LLM call (alcohol or no-photo note-only chat)
    # ------------------------------------------------------------------
    user_payload = {
        "customer_text": customer_text,
        "locale": client_locale,
        "cuisine": cuisine,
        "target_language": target_language,
        "extracted": {
            # Only safe/basic fields; do not pass allergens
            "alcohol_type": extracted.alcohol_type,
            "abv": extracted.abv,
            "volume_ml": extracted.volume_ml,
            "raw_text_snippet": extracted.raw_text_snippet,
        },
        "ocr_snippet": combined[:600],
    }

    try:
        llm_raw = call_llm(
            [
                {"role": "system", "content": system_prompt()},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ]
        )
        llm_out = enforce(llm_raw, target_language)
    except Exception:
        logging.error("LLM failed, returning fallback response.")
        llm_out = enforce(
            {"answer": "Sorry — something went wrong while generating the response. Please try again."},
            target_language,
        )

    sess["last_answer"] = llm_out["answer"]
    sess["last_payload"] = user_payload

    logging.info(f"Done: session_id={session_id} answer_snip={llm_out['answer'][:100]!r}")
    return {"status": "ok", "session_id": session_id, "llm": llm_out}


# ============================================================
# Routes
# ============================================================
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "welcome": WELCOME_MESSAGE_EN},
    )


@app.post("/api/analyze")
async def analyze(
    customer_text: str = Form(""),
    session_id: Optional[str] = Form(None),
    photos: Optional[List[UploadFile]] = File(None),
    client_locale: str = Form(""),
):
    n_photos = len(photos) if photos else 0
    logging.info(f"API /analyze: session_id={session_id!r} photos={n_photos} locale={client_locale!r}")
    return await analyze_impl(customer_text, session_id, photos or [], client_locale)


@app.post("/api/reset")
async def reset(payload: Dict[str, Any] = Body(...)):
    sid = payload.get("session_id")
    if sid and sid in SESSIONS:
        del SESSIONS[sid]
        logging.info(f"API /reset: cleared session_id={sid}")
    return {"status": "ok"}

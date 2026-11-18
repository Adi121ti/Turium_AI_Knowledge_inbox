import json
import os
import re
from typing import List

import numpy as np
import requests
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def build_note_title(content: str, fallback: str = 'Untitled note') -> str:
    raw_value = (content or '').strip()
    if not raw_value:
        return fallback

    first_line = ''
    for line in raw_value.splitlines():
        trimmed = normalize_whitespace(line)
        if trimmed:
            first_line = trimmed
            break

    candidate = first_line or normalize_whitespace(raw_value)
    if not candidate:
        return fallback

    sentences = re.split(r'(?<=[.!?])\s+', candidate)
    first_sentence = sentences[0].strip() if sentences else candidate
    if not first_sentence:
        return fallback

    words = first_sentence.split()
    if not words:
        return fallback

    selected = []
    current_length = 0
    for word in words:
        if len(word) > 60:
            return fallback
        addition = len(word) + (1 if selected else 0)
        if current_length + addition > 60:
            break
        selected.append(word)
        current_length += addition

    title = ' '.join(selected).strip()
    return title or fallback


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 120) -> List[str]:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return []

    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        piece = cleaned[start:end].strip()
        if not piece:
            break
        chunks.append(piece)
        if end == len(cleaned):
            break
        start = max(start + chunk_size - overlap, end - overlap)

    return [chunk for chunk in chunks if chunk]


def is_greeting_question(question: str) -> bool:
    text = normalize_whitespace(question or '').lower()
    if not text:
        return False
    text = text.strip('!?.,;:')
    greetings = {
        'hello', 'hi', 'hey', 'hey there', 'hi there', 'good morning', 'good evening', 'good afternoon', 'yo', 'greetings'
    }
    return text in greetings or text.startswith('hello ') or text.startswith('hi ') or text.startswith('hey ')


def build_agent_greeting_answer(question: str = '') -> str:
    greeting = 'Hi!' if not question else f"Hi!"
    return f"{greeting} I can help you search your saved notes and URLs. Ask me anything about your knowledge base, and I’ll answer from what you’ve saved."


class EmbeddingService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return cls._instance

    def embed(self, text: str):
        vector = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return [float(value) for value in np.asarray(vector).tolist()]


def fetch_url_content(url: str) -> str:
    browser_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
    }
    candidates = [url]
    if url.startswith("http://") or url.startswith("https://"):
        candidates.append(f"https://r.jina.ai/http://{url.split('://', 1)[1]}")

    last_error = None
    for candidate_url in candidates:
        try:
            response = requests.get(candidate_url, timeout=30, headers=browser_headers, allow_redirects=True)
            if response.status_code >= 400:
                raise requests.HTTPError(f"HTTP {response.status_code}")

            if not response.text or not response.text.strip():
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)
            if not text.strip():
                text = response.text.strip()
            return text[:20000]
        except Exception as exc:  # pragma: no cover - defensive fallback
            last_error = exc

    raise ValueError(f"Could not read content from URL: {last_error}")


def cosine_similarity(left_vector, right_vector):
    left = np.asarray(left_vector, dtype=float)
    right = np.asarray(right_vector, dtype=float)
    if left.size == 0 or right.size == 0:
        return 0.0
    denominator = np.linalg.norm(left) * np.linalg.norm(right)
    if denominator == 0:
        return 0.0
    return float(np.dot(left, right) / denominator)


def resolve_llm_provider(provider: str = None) -> str:
    requested = (provider or os.getenv("LLM_PROVIDER") or "").strip().lower()
    if requested in {"gemini", "google", "google-gemini"}:
        return "gemini"
    if requested in {"openai", "chatgpt"}:
        return "openai"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "fallback"


def _build_prompt_context(question: str, relevant_chunks, history=None) -> str:
    context_chunks = relevant_chunks[:3]
    context = "\n\n".join(f"Source {index + 1}: {chunk['content']}" for index, chunk in enumerate(context_chunks))

    if history:
        prior_messages = []
        for message in history:
            role = str(message.get('role') or 'user').strip()
            content = str(message.get('content') or message.get('text') or '').strip()
            if not content:
                continue
            prior_messages.append(f"{role.title()}: {content}")
        if prior_messages:
            return "\n\n".join(prior_messages + [f"User: {question}", f"Context:\n{context}"])

    return f"Question: {question}\n\nContext:\n{context}"


def _call_openai_provider(question: str, relevant_chunks, history=None):
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    client = OpenAI(api_key=api_key)
    context = _build_prompt_context(question, relevant_chunks, history=history)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You answer based only on the provided context. Cite sources by their number when possible."},
            {"role": "user", "content": context},
        ],
        temperature=0.2,
    )
    content = response.choices[0].message.content.strip()
    return content


def _call_gemini_provider(question: str, relevant_chunks, history=None):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    context = _build_prompt_context(question, relevant_chunks, history=history)
    payload = {
        "contents": [{"parts": [{"text": context}]}],
        "generationConfig": {"temperature": 0.2, "topP": 0.9},
    }
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}",
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    candidates = data.get('candidates') or []
    if not candidates:
        return None
    parts = candidates[0].get('content', {}).get('parts') or []
    for part in parts:
        if isinstance(part, dict) and part.get('text'):
            return part['text'].strip()
    return None


def build_rag_answer(question: str, relevant_chunks, history=None, provider: str = None):
    if is_greeting_question(question):
        return {
            "answer": build_agent_greeting_answer(question),
            "sources": [],
        }

    if not relevant_chunks:
        return {
            "answer": "I couldn't find enough relevant content in your saved items to answer that question.",
            "sources": [],
        }

    selected_provider = resolve_llm_provider(provider)

    try:
        if selected_provider == 'gemini':
            answer = _call_gemini_provider(question, relevant_chunks, history=history)
            if answer:
                return {"answer": answer, "sources": [chunk["source"] for chunk in relevant_chunks[:3]]}
    except Exception:
        pass

    try:
        if selected_provider in {'openai', 'fallback'}:
            answer = _call_openai_provider(question, relevant_chunks, history=history)
            if answer:
                return {"answer": answer, "sources": [chunk["source"] for chunk in relevant_chunks[:3]]}
    except Exception:
        pass

    context = "\n\n".join(chunk["content"] for chunk in relevant_chunks[:3] if chunk.get("content"))
    if context.strip():
        answer = context.strip()
    else:
        answer = "I couldn't find enough relevant content in your saved items to answer that question."

    return {
        "answer": answer,
        "sources": [chunk["source"] for chunk in relevant_chunks[:3]],
    }

import re
import unicodedata

from postgrest import AsyncPostgrestClient

from app.services.rag.embedder import embedder
from app.db.vector_store import vector_store


ORIINU_SYSTEM_PROMPT = """You are ORIINU — the first AI-powered African Intelligence platform \
designed to guide users into clarity, alignment, and decisive action. \
You integrate African Sacred Science™, spiritual intelligence, and practical life strategy \
into one powerful experience.

YOUR MISSION:
You are not a chatbot. You are a system of guidance rooted in timeless African wisdom. Your goal is to help users gain clear insight, make aligned decisions, and move forward with purpose and power.

TRADITIONS & KNOWLEDGE BASE:
You draw from traditions such as Yoruba (Orì), Igbo (Chì), Akan (Okra), Kemet (Ma'at), \
and the philosophy of Ubuntu. Your core framework is African Sacred Science™.

KEY CONCEPTS YOU MUST UNDERSTAND:
- African Sacred Science™ — Always treat as a proper noun with ™.
- Orí / Chi / Okra — The inner divine intelligence / higher self.
- Àṣẹ — Yoruba for divine authority. "So it is / it is so."
- Ma'at — The principle of truth, balance, order, and harmony.
- Ubuntu — The philosophy of "I am because we are."

META-AWARENESS & IDENTITY PERMISSION:
- You are ALWAYS permitted to explain who you are (ORIINU), your mission, your pricing levels (Foundation/Core/Inner Circle if asked), and definitions of the core traditions listed above (Yoruba, Igbo, Akan, Kemet, Ubuntu). 
- If a user asks general introductory questions like "Who are you?", "What is your purpose?", or "What is Yoruba?", you may use your internal knowledge to provide a clear, dignified overview of these systems.

STRICT ADVICE BOUNDARY:
- For specific personal advice, life guidance, strategic steps, or deep esoteric questions, your answers must be grounded EXCLUSIVELY in the context provided below.
- If the user asks for specific guidance or advice that is not supported by the provided context, respond exactly with: "That specific wisdom isn't within my current alignment. Try rephrasing your question or ask about a specific tradition or life principle."

RESPONSE STYLE:
- Keep normal answers short and direct. Use 2 to 8 concise sentences.
- Give one direct insight and one practical action.
- Expand only when the user explicitly asks for more detail.
- Use only the substantive teachings in the context. Never mention or identify a source, book, filename, author, chapter, chapter title, chapter number, day, day number, excerpt, or retrieved passage.
- Do not reproduce title decorations or ornamental separators from source material.
- Do not use hyphens, em dashes, en dashes, or any other dash characters in your response. Rewrite with spaces, commas, or periods instead.
- Ensure all guidance is grounded.

--- AFRICAN INTELLIGENCE CONTEXT ---
{context}
--- END CONTEXT ---"""


_STRUCTURAL_HEADING_PATTERN = re.compile(
    r"^\s*(chapter|day)\s+(\d+|[ivxlcdm]+|one|two|three|four|five|six|seven|"
    r"eight|nine|ten)\b(.*)$",
    re.IGNORECASE,
)
_AUTHOR_LINE_PATTERN = re.compile(
    r"^\s*(?:author|written\s+by|authored\s+by)\s*[:\-]?\s*.+$",
    re.IGNORECASE,
)
_BARE_BYLINE_PATTERN = re.compile(r"^\s*by\s+\S+(?:\s+\S+){0,8}\s*$", re.IGNORECASE)
_DECORATIVE_LINE_PATTERN = re.compile(r"^\s*[^\w\s]{2,}\s*$", re.UNICODE)
_CURRENT_SOURCE_TITLES = (
    "365 african proverbs",
    "african prosperity book",
    "olodumare updated",
    "olodumare workbook companion",
    "wealth power destiny",
)


def _normalize_source_line(line: str) -> str:
    normalized = unicodedata.normalize("NFKD", line)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[_\W]+", " ", normalized.lower(), flags=re.UNICODE)
    return " ".join(normalized.split())


def clean_retrieved_content(content: str) -> str:
    """Remove source structure while preserving the substantive excerpt text."""
    cleaned_lines: list[str] = []
    skip_next_title = False
    source_heading_seen = False

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue

        normalized = _normalize_source_line(stripped)
        if any(normalized.startswith(title) for title in _CURRENT_SOURCE_TITLES):
            source_heading_seen = True
            continue

        if _DECORATIVE_LINE_PATTERN.fullmatch(stripped):
            continue

        heading_match = _STRUCTURAL_HEADING_PATTERN.fullmatch(stripped)
        if heading_match:
            trailing_text = heading_match.group(3).strip(" \t:.-–—")
            skip_next_title = not trailing_text
            continue

        if skip_next_title:
            skip_next_title = False
            continue

        if _AUTHOR_LINE_PATTERN.fullmatch(stripped):
            continue

        if source_heading_seen and _BARE_BYLINE_PATTERN.fullmatch(stripped):
            source_heading_seen = False
            continue

        source_heading_seen = False
        cleaned_lines.append(stripped)

    while cleaned_lines and not cleaned_lines[-1]:
        cleaned_lines.pop()
    return "\n".join(cleaned_lines)


async def build_rag_prompt(
    user_message: str,
    client: AsyncPostgrestClient,
    top_k: int = 5,
    book_id: str = None,
) -> tuple[str, list[dict]]:
    query_embedding = embedder.embed_query(user_message)

    chunks = await vector_store.similarity_search(
        client=client,
        query_embedding=query_embedding,
        top_k=top_k,
        book_id=book_id,
    )

    context_parts = []
    for chunk in chunks:
        cleaned_content = clean_retrieved_content(chunk["content"])
        if cleaned_content:
            context_parts.append(cleaned_content)

    context = "\n\n".join(context_parts)
    system_prompt = ORIINU_SYSTEM_PROMPT.format(context=context)

    return system_prompt, chunks

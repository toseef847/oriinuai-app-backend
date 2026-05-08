import re
from typing import List


def chunk_by_day(text: str) -> List[dict]:
    """
    Splits the '365 African Proverbs' book by DAY entry.
    Each chunk contains one complete daily law including:
    Proverb, Wisdom, Sacred Insight, Reflection, Affirmation,
    Orí Decree, and Action Step.

    Returns list of dicts: {"content": str, "day_number": int, "law_name": str}
    """
    day_pattern = re.compile(
        r'(?:✅\s*)?DAY\s+(\d+)\s*[—–-]+\s*(.+?)(?=\n)',
        re.IGNORECASE
    )

    matches = list(day_pattern.finditer(text))
    chunks = []

    for i, match in enumerate(matches):
        day_number = int(match.group(1))
        law_name = match.group(2).strip()

        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        content = text[start:end].strip()

        if len(content) < 50:
            continue

        chunks.append({
            "content": content,
            "day_number": day_number,
            "law_name": law_name,
        })

    return chunks


def chunk_text_generic(text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
    """
    Fallback generic word-count chunker for future books
    that do NOT follow the daily entry structure.
    """
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.split()) >= 20:
            chunks.append(chunk.strip())
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks

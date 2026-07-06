import re


_DASH_CHARACTER_PATTERN = re.compile(
    r"[ \t]*[-\u058a\u05be\u1400\u1806\u2010-\u2015\u2e17\u2e1a"
    r"\u2e3a-\u2e3b\u2e40\u301c\u3030\u30a0\ufe31-\ufe32"
    r"\ufe58\ufe63\uff0d]+[ \t]*"
)


def remove_dash_characters(value: str) -> str:
    """Replace dash characters with spaces in generated assistant text."""
    return _DASH_CHARACTER_PATTERN.sub(" ", value)

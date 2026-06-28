"""
Sentence-aware text splitter for Russian and English meeting transcripts.
No external dependencies — uses regex only.
"""
import re

# Abbreviations that should not trigger sentence split
_ABBREVIATIONS_RU = {
    "т.е.", "т.д.", "и т.д.", "и т.п.", "т.п.", "и др.",
    "г.", "д.", "стр.", "п.", "ч.",
    "тел.", "моб.", "долл.", "руб.", "тыс.", "млн.", "млрд.",
    "рис.", "табл.", "прим.", "см.", "ср.",
}

_ABBREVIATIONS_EN = {
    "mr.", "mrs.", "ms.", "dr.", "prof.", "inc.", "ltd.",
    "vs.", "etc.", "dept.", "est.", "jr.", "sr.",
}

_ABBREVIATIONS = _ABBREVIATIONS_RU | _ABBREVIATIONS_EN


def _normalize_text(text: str) -> str:
    """Normalize whitespace in text."""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _has_abbreviation_before(text: str, pos: int) -> bool:
    """Check if position is right after a known abbreviation."""
    prefix = text[max(0, pos - 20):pos].strip().lower()
    for abbr in _ABBREVIATIONS:
        if prefix.endswith(abbr):
            return True
    return False


def split_sentences(text: str) -> list[str]:
    """
    Split text into sentences.
    Handles Russian and English with abbreviation protection.
    """
    text = _normalize_text(text)
    if not text:
        return []

    sentences = []
    current = []
    chars = list(text)
    i = 0
    n = len(chars)

    while i < n:
        current.append(chars[i])

        # Check for sentence-ending punctuation
        if chars[i] in '.!?':
            end_pos = i + 1

            if _has_abbreviation_before(text, end_pos):
                i += 1
                continue

            # Check if next char is space + uppercase, or end of string
            next_start = i + 1
            while next_start < n and chars[next_start] == ' ':
                next_start += 1

            if next_start >= n:
                sentences.append(''.join(current).strip())
                current = []
                i = next_start
                continue

            if next_start < n and (chars[next_start].isupper()
                                   or chars[next_start] in 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ«"'):
                sentences.append(''.join(current).strip())
                current = []
                i = next_start
                continue

        i += 1

    if current:
        remaining = ''.join(current).strip()
        if remaining:
            sentences.append(remaining)

    return sentences


def chunk_sentences(
    sentences: list[str],
    max_chars: int = 400,
    min_chars: int = 150,
    overlap: int = 1
) -> list[str]:
    """
    Group sentences into chunks with overlap.

    Each chunk: 2-4 sentences, ~150-400 chars.
    Overlapping sentence N+1 becomes first sentence of chunk N+1.

    Args:
        sentences: List of sentence strings.
        max_chars: Maximum characters per chunk.
        min_chars: Minimum characters per chunk.
        overlap: Number of overlapping sentences. Default 1.

    Returns:
        List of chunk strings.
    """
    if not sentences:
        return []

    chunks = []
    i = 0

    while i < len(sentences):
        chunk_sents = []
        chunk_len = 0

        j = i
        while j < len(sentences):
            s_len = len(sentences[j]) + 1
            if chunk_len + s_len > max_chars and chunk_sents:
                break
            chunk_sents.append(sentences[j])
            chunk_len += s_len
            j += 1

            if chunk_len >= min_chars and len(chunk_sents) >= 2:
                if j < len(sentences) and chunk_len + len(sentences[j]) + 1 <= max_chars + 50:
                    continue
                break

        if chunk_sents:
            chunks.append(' '.join(chunk_sents))

        if overlap > 0 and i + overlap < len(sentences):
            i = j - overlap
            if i <= (j - len(chunk_sents)):
                i = j - len(chunk_sents) + 1
        else:
            i = j

    return chunks


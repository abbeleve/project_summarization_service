"""
Merge diarization segments with forced-aligned word timestamps.

Algorithm (WhisperX-style):
  1. For each forced-aligned word, find the best overlapping diarization segment
     using a two-pointer sweep (both lists are sorted by time, O(N+M)).
  2. Assign the speaker with the highest overlap ratio.
  3. Words falling in gaps get the nearest speaker by segment *boundary*
     with a maximum distance cap.
  4. Consecutive same-speaker words are grouped into final transcript segments.
"""
import logging
import re
from dataclasses import dataclass
from typing import List

from core.diarization.base import DiarizationSegment

logger = logging.getLogger(__name__)

# Maximum gap (seconds) for fallback nearest-speaker assignment.
# If the nearest segment boundary is farther than this, the word
# is dropped entirely instead of being attached to a distant speaker.
_MAX_NEAREST_DISTANCE = 3.0


@dataclass
class AlignedWord:
    """A single word with its forced-alignment timestamp."""
    text: str
    start: float
    end: float
    speaker: str = "UNKNOWN"


@dataclass
class FinalSegment:
    """Output segment with speaker label and assembled text."""
    speaker: str
    start: float
    stop: float
    text: str


def merge(
    diarization_segments: List[DiarizationSegment],
    aligned_words: List[AlignedWord],
    overlap_threshold: float = 0.0,
) -> List[FinalSegment]:
    """
    Merge forced-aligned words with diarization segments.

    Both input lists MUST be sorted ascending by time.

    Args:
        diarization_segments: Speaker segments from pyannote.
        aligned_words: Word-level timestamps from forced-aligner.
        overlap_threshold: Minimum overlap fraction to assign a speaker
                           (default 0.0 — any overlap is enough).

    Returns:
        Grouped segments with speaker labels.
    """
    if not diarization_segments:
        logger.warning("No diarization segments — all words marked UNKNOWN")
        return _fallback_no_diarization(aligned_words)
    if not aligned_words:
        logger.warning("No aligned words — returning empty result")
        return []

    # --- Step 1: Assign speaker via two-pointer sweep O(N+M) ---
    _assign_speakers_two_pointer(
        aligned_words, diarization_segments, overlap_threshold,
    )

    # Drop words that didn't fall into any speaker segment
    kept_before = len(aligned_words)
    aligned_words = [w for w in aligned_words if w.speaker != "UNKNOWN"]
    dropped = kept_before - len(aligned_words)
    if dropped:
        logger.debug(f"Dropped {dropped} gap words (no overlapping diarization segment)")

    if not aligned_words:
        logger.warning("All words dropped — no overlap with any diarization segment")
        return []

    # --- Step 2: Group consecutive same-speaker words ---
    return _group_by_speaker(aligned_words)


# ---------------------------------------------------------------------------
# Two-pointer speaker assignment  (O(N+M))
# ---------------------------------------------------------------------------


def _assign_speakers_two_pointer(
    words: List[AlignedWord],
    segments: List[DiarizationSegment],
    threshold: float,
) -> None:
    """
    Sweep both sorted lists with a single pass, keeping a small sliding
    window of candidate diarization segments that can overlap the current word.
    """
    seg_idx = 0
    n_segs = len(segments)

    for word in words:
        word_duration = word.end - word.start
        if word_duration < 0:
            word.speaker = "UNKNOWN"
            continue

        word_mid = (word.start + word.end) / 2

        # Advance seg_idx so it points at the first segment that could overlap
        while seg_idx < n_segs and segments[seg_idx].stop <= word.start:
            seg_idx += 1

        # Look at a small window around the current position
        best_speaker = "UNKNOWN"
        best_overlap = 0.0
        best_boundary_dist = _MAX_NEAREST_DISTANCE + 1.0  # beyond cap

        scan_start = max(0, seg_idx - 1)  # one behind (gap fallback)
        scan_end = min(n_segs, seg_idx + 2)  # one ahead

        for i in range(scan_start, scan_end):
            dseg = segments[i]

            overlap_start = max(word.start, dseg.start)
            overlap_end = min(word.end, dseg.stop)
            overlap = max(0.0, overlap_end - overlap_start)

            if overlap > 0:
                ratio = overlap / word_duration
                if ratio > best_overlap:
                    best_overlap = ratio
                    best_speaker = dseg.speaker
            elif best_overlap <= threshold:
                # No overlap — measure distance to nearest boundary
                dist = min(
                    abs(word_mid - dseg.start),
                    abs(word_mid - dseg.stop),
                )
                if dist < best_boundary_dist:
                    best_boundary_dist = dist
                    best_speaker = dseg.speaker if dist <= _MAX_NEAREST_DISTANCE else "UNKNOWN"

        # Если у слова нулевая длительность — точка word.start известна, и если
        # она внутри сегмента диаризации, назначаем этого спикера безусловно.
        # Boundary-distance для zero-duration слов неинформативна: сегмент шире
        # 2*_MAX_NEAREST_DISTANCE даст UNKNOWN, хотя слово внутри.
        if word_duration == 0:
            containing_speaker = None
            for i in range(scan_start, scan_end):
                dseg = segments[i]
                if dseg.start <= word.start <= dseg.stop:
                    containing_speaker = dseg.speaker
                    break
            if containing_speaker is not None:
                if containing_speaker != best_speaker:
                    logger.debug(
                        f"Word '{word.text}' at {word.start:.2f}s: zero-duration word inside "
                        f"{containing_speaker} [{dseg.start:.2f}-{dseg.stop:.2f}], "
                        f"correcting from {best_speaker}"
                    )
                    best_speaker = containing_speaker

        if best_overlap <= threshold and best_speaker == "UNKNOWN":
            logger.debug(
                f"Word '{word.text}' [{word.start:.2f}-{word.end:.2f}]: "
                f"gap > {_MAX_NEAREST_DISTANCE}s, marked UNKNOWN"
            )

        word.speaker = best_speaker


# ---------------------------------------------------------------------------
# Grouping & segment assembly
# ---------------------------------------------------------------------------


def _group_by_speaker(aligned_words: List[AlignedWord]) -> List[FinalSegment]:
    """
    Group consecutive words with the same speaker into FinalSegments.
    """
    if not aligned_words:
        return []

    result: List[FinalSegment] = []
    current_words: List[AlignedWord] = [aligned_words[0]]

    for word in aligned_words[1:]:
        if word.speaker == current_words[-1].speaker:
            current_words.append(word)
        else:
            result.append(_words_to_segment(current_words))
            current_words = [word]

    if current_words:
        result.append(_words_to_segment(current_words))

    return result


def _words_to_segment(words: List[AlignedWord]) -> FinalSegment:
    """
    Merge a list of same-speaker words into a single FinalSegment.

    Strips leading/trailing whitespace from each word to avoid double-spaces
    from tokenizers, then joins with a single space.
    """
    cleaned = [w.text.strip() for w in words if w.text.strip()]
    return FinalSegment(
        speaker=words[0].speaker,
        start=words[0].start,
        stop=words[-1].end,
        text=" ".join(cleaned),
    )


def _fallback_no_diarization(
    aligned_words: List[AlignedWord],
) -> List[FinalSegment]:
    """
    When diarization produced no segments, return words as a single UNKNOWN block.
    """
    if not aligned_words:
        return []
    cleaned = [w.text.strip() for w in aligned_words if w.text.strip()]
    return [
        FinalSegment(
            speaker="UNKNOWN",
            start=aligned_words[0].start,
            stop=aligned_words[-1].end,
            text=" ".join(cleaned),
        )
    ]


# ---------------------------------------------------------------------------
# Punctuation restoration
# ---------------------------------------------------------------------------


def _is_word_char(ch: str) -> bool:
    """Return True if *ch* is an alphanumeric / underscore character (``\\w``)."""
    return bool(re.match(r'\w', ch))


def _scan_trailing_punct(text: str, word_end: int) -> str:
    """
    Collect non-word characters immediately after *word_end*.

    Stops at (in order of precedence):
      1. End of string
      2. A word character (``\\w``) — start of the next word
      3. A space character — inter-word punctuation belongs to the preceding
         word only when adjacent; punctuation separated by a space (e.g.
         the parenthesis in ``Hello, (world)``) belongs to the *next* word.
    """
    punct: list[str] = []
    pos = word_end
    while pos < len(text):
        ch = text[pos]
        if _is_word_char(ch) or ch.isspace():
            break
        punct.append(ch)
        pos += 1
    return ''.join(punct)


def _scan_leading_punct(text: str, word_start: int, left_limit: int) -> str:
    """
    Collect non-word characters immediately before *word_start*.

    Stops at (in order of precedence):
      1. *left_limit* (the end of the previous consumed token)
      2. A word character (``\\w``) — end of the previous word
      3. A space character — punctuation separated by a space belongs
         to the preceding word, not this one.
    """
    punct: list[str] = []
    scan = word_start - 1
    while scan >= left_limit:
        ch = text[scan]
        if _is_word_char(ch) or ch.isspace():
            break
        punct.insert(0, ch)
        scan -= 1
    return ''.join(punct)


def restore_punctuation(
    aligned_words: List[AlignedWord],
    original_text: str,
) -> List[AlignedWord]:
    """
    Project punctuation from the original ASR text back onto aligned words.

    The forced aligner's internal tokenizer strips punctuation from words
    (e.g., ``"Привет,"`` → ``"Привет"``).  This function maps each aligned
    word to its occurrence in the original ASR text and re-attaches the
    surrounding punctuation.

    Handles:
      - Hyphenated words (``из-за``, ``кое-кто``)
      - Trailing punctuation (``.,!?:;—…»)"'`` etc.)
      - Leading punctuation (``«„"'([{`` etc.)
      - Multiple consecutive punctuation characters (e.g. ``...``, ``!?``)
      - ASR hallucination gaps (extra aligner words without original match)
      - Dropped words (aligner skips a word from the original text)
      - Case mismatches between aligner output and original text
    """
    if not aligned_words or not original_text:
        return aligned_words

    # Tokenize the original text at word boundaries, capturing hyphenated words.
    orig_tokens = [
        (m.start(), m.end())
        for m in re.finditer(r'\w+(?:-\w+)*', original_text)
    ]
    total_orig = len(orig_tokens)

    result: List[AlignedWord] = []
    orig_idx = 0

    for word in aligned_words:
        clean = word.text.strip().lower()
        if not clean:
            result.append(word)
            continue

        # Search forward from the current position for a matching token.
        # Use a local pointer so we can roll back if the aligner word
        # doesn't appear in the original (hallucination).
        matched: tuple[int, int] | None = None
        matched_offset = orig_idx

        while matched_offset < total_orig:
            start, end = orig_tokens[matched_offset]
            if original_text[start:end].lower() == clean:
                matched = (start, end)
                break
            matched_offset += 1

        if matched is None:
            # Hallucinated word — return as-is, don't advance the token pointer
            result.append(word)
            continue

        matched_start, matched_end = matched

        # Leading punctuation: collect non-word, non-space chars between
        # the end of the previous consumed token and this word's start.
        prev_end = orig_tokens[orig_idx - 1][1] if orig_idx > 0 else 0
        leading = (
            ''
            if prev_end == matched_start
            else _scan_leading_punct(original_text, matched_start, prev_end)
        )

        # Trailing punctuation: collect non-word chars immediately after
        # the word, stopping at the first space or word character.
        trailing = _scan_trailing_punct(original_text, matched_end)

        # Preserve original casing from the ASR text
        restored = leading + original_text[matched_start:matched_end] + trailing
        result.append(AlignedWord(
            text=restored,
            start=word.start,
            end=word.end,
        ))

        # Advance the token pointer past the consumed token
        orig_idx = matched_offset + 1

    return result

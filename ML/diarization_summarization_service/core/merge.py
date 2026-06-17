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
        if word_duration <= 0:
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

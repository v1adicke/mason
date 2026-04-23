"""Task matching helpers for Obsidian tasks"""

from __future__ import annotations

from difflib import SequenceMatcher
import re


MIN_MATCH_SCORE = 0.6


def _extract_task_text(line: str) -> str:
    """Extract pure task text from markdown checkbox line"""
    clean_line = line.strip()
    if clean_line.startswith("- [ ] ") or clean_line.startswith("- [x] "):
        return clean_line[6:].strip()
    return clean_line


def _normalize_text(value: str) -> str:
    """Normalize text for fuzzy task matching."""
    lowered = value.lower().strip()
    return re.sub(r"[^a-zа-я0-9\s]", " ", lowered, flags=re.IGNORECASE)


def _task_match_score(query: str, candidate: str) -> float:
    """Calculate similarity score between query and candidate task"""
    query_norm = _normalize_text(query)
    candidate_norm = _normalize_text(candidate)
    if not query_norm or not candidate_norm:
        return 0.0

    if query_norm in candidate_norm or candidate_norm in query_norm:
        return 1.0

    return SequenceMatcher(a=query_norm, b=candidate_norm).ratio()


def _find_task_matches(lines: list[str], task_text: str) -> list[tuple[int, str, float]]:
    """Find matching checkbox tasks by substring and fuzzy similarity"""
    matches: list[tuple[int, str, float]] = []
    for index, line in enumerate(lines):
        line_lower = line.lower()
        if "- [ ]" not in line_lower and "- [x]" not in line_lower:
            continue

        candidate = _extract_task_text(line)
        score = _task_match_score(task_text, candidate)
        if score >= MIN_MATCH_SCORE:
            matches.append((index, candidate, score))

    matches.sort(key=lambda item: item[2], reverse=True)
    return matches

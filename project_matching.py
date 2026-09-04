"""Safe project-name matching for multi-PDF workflows."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
import re

from project_discovery import ProjectDiscovery, ProjectCandidate, normalize_project_name


# Words commonly introduced by document-specific naming rather than the core project.
_CONTEXT_TOKENS = {
    "proje", "project", "name", "faz", "phase", "ahu", "unit", "g", "grup", "group",
    "rev", "revision", "revizyon", "drawing", "elektrik", "uretim", "üretim",
}


def _tokens(value: str | None) -> list[str]:
    return [token for token in normalize_project_name(value or "").split() if token]


def _core_tokens(value: str | None) -> set[str]:
    return {t for t in _tokens(value) if t not in _CONTEXT_TOKENS}


def _compact(value: str | None) -> str:
    return "".join(_tokens(value))


def _numeric_tokens(value: str | None) -> set[str]:
    return set(re.findall(r"\d+", normalize_project_name(value or "")))


def _matching_display_name(value: str | None) -> str | None:
    """Remove a document-label prefix for non-exact human-readable matches."""
    if value is None:
        return None
    return re.sub(r"^\s*project\s+", "", value, flags=re.I).strip() or value


@dataclass(frozen=True)
class ProjectMatch:
    left_name: str | None
    right_name: str | None
    left_normalized: str | None
    right_normalized: str | None
    score: float
    status: str
    reason: str
    left_source: str | None = None
    right_source: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def score_project_names(left: str | None, right: str | None) -> tuple[float, str, str]:
    """Return (score 0..1, status, reason) for two project names."""
    left_n = normalize_project_name(left or "")
    right_n = normalize_project_name(right or "")
    if not left_n or not right_n:
        return 0.0, "NO_MATCH", "missing project name"
    if left_n == right_n:
        return 1.0, "EXACT", "normalized project names are identical"

    left_core = _core_tokens(left_n)
    right_core = _core_tokens(right_n)
    if not left_core or not right_core:
        return 0.0, "NO_MATCH", "no usable core project tokens"

    intersection = left_core & right_core
    union = left_core | right_core
    jaccard = len(intersection) / len(union) if union else 0.0
    coverage = len(intersection) / max(1, min(len(left_core), len(right_core)))
    sequence = SequenceMatcher(None, _compact(left_n), _compact(right_n)).ratio()

    left_nums = _numeric_tokens(left_n)
    right_nums = _numeric_tokens(right_n)
    numeric_conflict = bool(left_nums and right_nums and left_nums.isdisjoint(right_nums))

    score = min(1.0, 0.50 * jaccard + 0.35 * coverage + 0.15 * sequence)

    if numeric_conflict and len(intersection) < 4:
        return min(score, 0.55), "REVIEW_REQUIRED", "project names share text but numeric identifiers conflict"
    if coverage >= 0.80 and jaccard >= 0.60 and len(intersection) >= 3:
        return max(score, 0.85), "HIGH_CONFIDENCE", "strong common core project name"
    if coverage >= 0.60 and jaccard >= 0.40:
        return score, "MEDIUM_CONFIDENCE", "partially matching core project name"
    if score >= 0.75:
        return score, "REVIEW_REQUIRED", "similar text requires manual confirmation"
    return score, "NO_MATCH", "insufficient project-name agreement"


def match_project_names(left: str | None, right: str | None, *, left_source: str | None = None, right_source: str | None = None) -> ProjectMatch:
    score, status, reason = score_project_names(left, right)
    return ProjectMatch(
        left_name=left,
        right_name=right,
        left_normalized=normalize_project_name(left or "") or None,
        right_normalized=normalize_project_name(right or "") or None,
        score=round(score, 4),
        status=status,
        reason=reason,
        left_source=left_source,
        right_source=right_source,
    )


def _best_candidate(discovery: ProjectDiscovery, target: ProjectDiscovery) -> tuple[ProjectCandidate | None, float, str, str]:
    best = None
    best_tuple = (None, -1.0, "NO_MATCH", "")
    left_candidates = discovery.candidates or ()
    right_candidates = target.candidates or ()
    for left in left_candidates:
        for right in right_candidates:
            score, status, reason = score_project_names(left.value, right.value)
            if score > best_tuple[1]:
                best_tuple = (right, score, status, reason)
        if best_tuple[0] is not None and best_tuple[1] >= 1.0:
            break
    return best_tuple


def match_discoveries(left: ProjectDiscovery, right: ProjectDiscovery) -> ProjectMatch:
    """Match two discovery objects, considering all retained candidates.

    Exact normalized matches preserve the raw discovered value. For a non-exact
    match, a leading document-label ``Project`` is removed from the display value
    while the normalized/source data remains faithful to discovery.
    """
    candidate, score, status, reason = _best_candidate(left, right)
    right_raw = candidate.value if candidate else right.project_name
    left_raw = left.project_name
    if status != "EXACT":
        left_display = _matching_display_name(left_raw)
        right_display = _matching_display_name(right_raw)
    else:
        left_display = left_raw
        right_display = right_raw

    return ProjectMatch(
        left_name=left_display,
        right_name=right_display,
        left_normalized=left.project_name_normalized,
        right_normalized=normalize_project_name(right_raw or "") or None,
        score=round(max(score, 0.0), 4),
        status=status,
        reason=reason,
        left_source=left.project_source,
        right_source=candidate.source if candidate else right.project_source,
    )


def match_discovery_lists(left_items: list[ProjectDiscovery], right_items: list[ProjectDiscovery]) -> list[ProjectMatch]:
    """Return one-to-one greedy best project matches for two collections."""
    pairs: list[tuple[float, int, int, ProjectMatch]] = []
    for i, left in enumerate(left_items):
        for j, right in enumerate(right_items):
            match = match_discoveries(left, right)
            pairs.append((match.score, i, j, match))

    output: list[ProjectMatch] = []
    used_left: set[int] = set()
    used_right: set[int] = set()
    for _, i, j, match in sorted(pairs, reverse=True, key=lambda item: item[0]):
        if i in used_left or j in used_right:
            continue
        output.append(match)
        used_left.add(i)
        used_right.add(j)
    return output

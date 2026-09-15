"""Project-name matching based on shared words, without project-specific whitelists."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
import re

from app_logger import debug, exception, info
from project_discovery import ProjectDiscovery, normalize_project_name


_TOKEN_FUZZY_THRESHOLD = 0.86


def _tokens(value: str | None) -> list[str]:
    """Return every normalized word; no whitelist/blacklist is applied."""
    return [token for token in normalize_project_name(value or "").split() if token]


def _compact(value: str | None) -> str:
    return "".join(_tokens(value))


def _numeric_tokens(value: str | None) -> set[str]:
    return set(re.findall(r"\d+", normalize_project_name(value or "")))


def _token_similarity(left: str, right: str) -> float:
    """Compare two words exactly first, then tolerate small OCR/spelling differences."""
    if left == right:
        return 1.0
    shorter, longer = sorted((left, right), key=len)
    if len(shorter) >= 4 and longer.startswith(shorter):
        return 0.94
    return SequenceMatcher(None, left, right).ratio()


def _shared_word_matches(left_tokens: list[str], right_tokens: list[str]) -> list[tuple[float, str, str]]:
    """Find shared words/fuzzy-equivalent words without filtering any token."""
    candidates: list[tuple[float, str, str]] = []
    for left in set(left_tokens):
        for right in set(right_tokens):
            similarity = _token_similarity(left, right)
            if similarity >= _TOKEN_FUZZY_THRESHOLD:
                candidates.append((similarity, left, right))

    used_left: set[str] = set()
    used_right: set[str] = set()
    matches: list[tuple[float, str, str]] = []
    for similarity, left, right in sorted(candidates, reverse=True):
        if left in used_left or right in used_right:
            continue
        used_left.add(left)
        used_right.add(right)
        matches.append((similarity, left, right))
    return matches


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
    """Match projects purely from their words.

    There is intentionally no project/customer whitelist and no context-token
    blacklist. If at least one complete normalized word is shared, the names
    are considered a project match. Fuzzy word matching also handles small
    spelling/OCR/inflection differences such as ``yatirim``/``yatirimi``.
    """
    try:
        left_n = normalize_project_name(left or "")
        right_n = normalize_project_name(right or "")
        if not left_n or not right_n:
            return 0.0, "NO_MATCH", "missing project name"
        if left_n == right_n:
            return 1.0, "EXACT", "normalized project names are identical"

        left_tokens = _tokens(left_n)
        right_tokens = _tokens(right_n)
        matches = _shared_word_matches(left_tokens, right_tokens)

        if not matches:
            sequence = SequenceMatcher(None, _compact(left_n), _compact(right_n)).ratio()
            if sequence >= 0.90:
                return round(sequence, 4), "HIGH_CONFIDENCE", "very similar project labels"
            return 0.0, "NO_MATCH", "no common project word"

        # One shared word is deliberately sufficient. More shared words simply
        # increase the score/confidence; no numeric conflict can cancel a shared
        # word because the requested rule is word-driven matching.
        matched_count = len(matches)
        total_left = len(set(left_tokens))
        total_right = len(set(right_tokens))
        min_tokens = min(total_left, total_right) or 1
        max_tokens = max(total_left, total_right) or 1
        average_quality = sum(item[0] for item in matches) / matched_count
        coverage = matched_count / min_tokens
        balance = matched_count / max_tokens
        sequence = SequenceMatcher(None, _compact(left_n), _compact(right_n)).ratio()

        # Any shared word => MATCH. The score is informative only.
        score = min(
            1.0,
            0.60 * coverage
            + 0.20 * balance
            + 0.15 * average_quality
            + 0.05 * sequence,
        )
        if matched_count == 1:
            score = max(score, 0.50)
            return round(score, 4), "MATCH", "at least one common project word"

        score = max(score, 0.75)
        if coverage >= 0.75:
            return round(score, 4), "HIGH_CONFIDENCE", "multiple common project words"
        return round(score, 4), "MATCH", "multiple common project words"
    except Exception as exc:
        exception("Proje eşleşme skoru hesaplama hatası", exc, left=left, right=right)
        raise


def match_project_names(left, right, *, left_source=None, right_source=None) -> ProjectMatch:
    score, status, reason = score_project_names(left, right)
    return ProjectMatch(
        left,
        right,
        normalize_project_name(left or "") or None,
        normalize_project_name(right or "") or None,
        round(score, 4),
        status,
        reason,
        left_source,
        right_source,
    )


def _best_candidate(discovery: ProjectDiscovery, target: ProjectDiscovery):
    best_tuple = (None, -1.0, "NO_MATCH", "")
    target_candidates = tuple(target.candidates or ())
    exact = {}
    for candidate in target_candidates:
        exact.setdefault(candidate.normalized or normalize_project_name(candidate.value), candidate)

    for left in discovery.candidates or ():
        left_normalized = left.normalized or normalize_project_name(left.value)
        exact_candidate = exact.get(left_normalized)
        if exact_candidate is not None:
            return exact_candidate, 1.0, "EXACT", "normalized project candidate is identical"
        for right in target_candidates:
            score, status, reason = score_project_names(left.value, right.value)
            if score > best_tuple[1]:
                best_tuple = (right, score, status, reason)
    return best_tuple


def match_discoveries(left: ProjectDiscovery, right: ProjectDiscovery) -> ProjectMatch:
    try:
        candidate, score, status, reason = _best_candidate(left, right)
        right_raw = candidate.value if candidate else right.project_name
        left_raw = left.project_name
        result = ProjectMatch(
            left_raw,
            right_raw,
            left.project_name_normalized,
            normalize_project_name(right_raw or "") or None,
            round(max(score, 0.0), 4),
            status,
            reason,
            left.project_source,
            candidate.source if candidate else right.project_source,
        )
        debug("Discovery nesneleri proje eşleşti", left=left_raw, right=right_raw, score=result.score, status=status, reason=reason)
        return result
    except Exception as exc:
        exception("Project discovery eşleştirme hesaplama hatası", exc, left=left.project_name, right=right.project_name)
        raise


def match_discoveries_with_identifiers(left, right, left_text="", right_text="") -> ProjectMatch:
    base = match_discoveries(left, right)
    shared = _extract_id_from_text(left_text) & _extract_id_from_text(right_text)
    if shared:
        return ProjectMatch(
            base.left_name,
            base.right_name,
            base.left_normalized,
            base.right_normalized,
            1.0,
            "IDENTIFIER_MATCH",
            f"shared project/order identifier: {sorted(shared)}",
            base.left_source,
            base.right_source,
        )
    return base


def _extract_id_from_text(value: str | None) -> set[str]:
    if not value:
        return set()
    return set(re.findall(r"(?<![A-Z])\d{5,}(?!\d)", value.upper()))


def match_discovery_lists(left_items, right_items):
    left_norm = {
        item.project_name_normalized: (index, item)
        for index, item in enumerate(left_items)
        if item.project_name_normalized
    }
    right_norm = {
        item.project_name_normalized: (index, item)
        for index, item in enumerate(right_items)
        if item.project_name_normalized
    }
    output = []
    used_left = set()
    used_right = set()

    for normalized, (i, left) in left_norm.items():
        pair = right_norm.get(normalized)
        if pair is not None:
            j, right = pair
            output.append(match_discoveries(left, right))
            used_left.add(i)
            used_right.add(j)

    pairs = []
    for i, left in enumerate(left_items):
        if i in used_left:
            continue
        for j, right in enumerate(right_items):
            if j in used_right:
                continue
            match = match_discoveries(left, right)
            pairs.append((match.score, i, j, match))

    for _, i, j, match in sorted(pairs, reverse=True, key=lambda item: item[0]):
        if i in used_left or j in used_right:
            continue
        if match.status == "NO_MATCH":
            continue
        output.append(match)
        used_left.add(i)
        used_right.add(j)

    info(
        "Toplu proje eşleştirmesi hesaplandı",
        pdf1_count=len(left_items),
        pdf2_count=len(right_items),
        match_count=len(output),
    )
    return output

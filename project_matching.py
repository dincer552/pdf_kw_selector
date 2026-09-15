"""Project-name matching for inconsistent engineering PDF labels."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
import re

from app_logger import debug, exception, info
from project_discovery import ProjectDiscovery, normalize_project_name

# No project/customer whitelist is used here. Every word in the discovered
# project name is eligible to participate in matching. This is intentional:
# a future project may contain any new customer/site/project word and must not
# require a code change just because that word was never seen before.
_TOKEN_FUZZY_THRESHOLD = 0.86


def _tokens(value: str | None) -> list[str]:
    return [token for token in normalize_project_name(value or "").split() if token]


def _compact(value: str | None) -> str:
    return "".join(_tokens(value))


def _numeric_tokens(value: str | None) -> set[str]:
    return set(re.findall(r"\d+", normalize_project_name(value or "")))


def _token_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    shorter, longer = sorted((left, right), key=len)
    if len(shorter) >= 5 and longer.startswith(shorter):
        return 0.94
    return SequenceMatcher(None, left, right).ratio()


def _match_tokens(left_tokens: list[str], right_tokens: list[str]) -> tuple[list[float], set[str]]:
    """Pair words once; exact equality is preferred over fuzzy similarity."""
    candidates = []
    for left in left_tokens:
        for right in right_tokens:
            similarity = _token_similarity(left, right)
            if similarity >= _TOKEN_FUZZY_THRESHOLD:
                candidates.append((similarity, left, right))

    used_left: set[str] = set()
    used_right: set[str] = set()
    similarities: list[float] = []
    for similarity, left, right in sorted(candidates, reverse=True):
        if left in used_left or right in used_right:
            continue
        used_left.add(left)
        used_right.add(right)
        similarities.append(similarity)
    return similarities, used_left


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
    """Compare project names using all words; one shared word is sufficient.

    There is deliberately no whitelist/blacklist of project words. Exact or
    fuzzy matching is performed against every word discovered in both names.
    Therefore a completely new customer, city, site, person, or project word
    can establish a match without modifying this module.
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
        if not left_tokens or not right_tokens:
            return 0.0, "NO_MATCH", "no project words"

        similarities, matched_left = _match_tokens(left_tokens, right_tokens)
        matched_count = len(similarities)
        if matched_count == 0:
            sequence = SequenceMatcher(None, _compact(left_n), _compact(right_n)).ratio()
            if sequence >= 0.94:
                return round(sequence, 4), "HIGH_CONFIDENCE", "very similar project labels"
            return 0.0, "NO_MATCH", "no matching project words"

        min_word_count = min(len(left_tokens), len(right_tokens))
        max_word_count = max(len(left_tokens), len(right_tokens))
        coverage = matched_count / min_word_count if min_word_count else 0.0
        jaccard_like = matched_count / (len(left_tokens) + len(right_tokens) - matched_count)
        token_quality = sum(similarities) / matched_count
        sequence = SequenceMatcher(None, _compact(left_n), _compact(right_n)).ratio()

        left_nums = _numeric_tokens(left_n)
        right_nums = _numeric_tokens(right_n)
        numeric_conflict = bool(left_nums and right_nums and left_nums.isdisjoint(right_nums))

        # Shared words are the primary signal. Whole-name similarity is only a
        # secondary signal and cannot turn a zero-word match into a match.
        score = min(
            1.0,
            0.55 * jaccard_like
            + 0.20 * coverage
            + 0.10 * token_quality
            + 0.15 * sequence,
        )

        # User requirement: even ONE shared word is enough to put the pair in
        # the same project-matching pipeline. Numeric conflicts do not cancel
        # the shared-word match; they only lower its confidence score.
        if matched_count == 1:
            if numeric_conflict:
                return max(round(score * 0.75, 4), 0.35), "MATCH", "one shared project word; numeric values differ"
            return max(round(score, 4), 0.50), "MATCH", "one shared project word"

        if numeric_conflict:
            return max(round(score * 0.85, 4), 0.55), "MATCH", "multiple shared project words; numeric values differ"

        if matched_count >= 2 and coverage >= 0.80:
            return max(round(score, 4), 0.85), "HIGH_CONFIDENCE", "multiple shared project words"
        return max(round(score, 4), 0.65), "MATCH", "shared project words"
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
        debug(
            "Discovery nesneleri proje eşleşti",
            left=left_raw,
            right=right_raw,
            score=result.score,
            status=status,
            reason=reason,
        )
        return result
    except Exception as exc:
        exception(
            "Project discovery eşleştirme hesaplama hatası",
            exc,
            left=left.project_name,
            right=right.project_name,
        )
        raise


def _extract_id_from_text(value: str | None) -> set[str]:
    if not value:
        return set()
    return set(re.findall(r"(?<![A-Z])\d{5,}(?!\d)", value.upper()))


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

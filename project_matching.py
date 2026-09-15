"""Robust project-name matching for inconsistent engineering PDF labels."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
import re

from app_logger import debug, exception, info
from project_discovery import ProjectDiscovery, normalize_project_name

# Words that commonly describe document metadata rather than project identity.
# These are deliberately generic so new projects do not require hard-coded
# aliases.  Distinctive customer/project words are kept as identity tokens.
_CONTEXT_TOKENS = {
    "proje", "project", "name", "projectname", "prj", "projectno",
    "ordernumber", "orderno", "order", "unitnumber", "unitreference",
    "revision", "revizyon", "revisionno", "revisiondate", "creationdate",
    "date", "faz", "phase", "ahu", "unit", "grup", "group", "drawing",
    "elektrik", "electric", "production", "uretim", "engineering",
    "yeni", "new", "fabrika", "factory", "yatirim", "investment",
    "yatirimi", "urun", "urunleri", "products", "product", "series", "seri",
}

_MIN_DISTINCTIVE_TOKEN_LEN = 4
_TOKEN_FUZZY_THRESHOLD = 0.86


def _tokens(value: str | None) -> list[str]:
    return [token for token in normalize_project_name(value or "").split() if token]


def _core_tokens(value: str | None) -> set[str]:
    return {
        token for token in _tokens(value)
        if token not in _CONTEXT_TOKENS and len(token) >= _MIN_DISTINCTIVE_TOKEN_LEN
    }


def _compact(value: str | None) -> str:
    return "".join(_tokens(value))


def _numeric_tokens(value: str | None) -> set[str]:
    return set(re.findall(r"\d+", normalize_project_name(value or "")))


def _token_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    # Handles common Turkish/English inflection or truncation such as
    # yatirim/yatirimi after generic-word filtering, and minor OCR variants.
    shorter, longer = sorted((left, right), key=len)
    if len(shorter) >= 5 and longer.startswith(shorter):
        return 0.94
    return SequenceMatcher(None, left, right).ratio()


def _match_core_tokens(left_tokens: set[str], right_tokens: set[str]) -> tuple[list[float], set[str]]:
    """Greedily pair each distinctive token at most once."""
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
    """Score project names without maintaining a per-project alias list.

    Matching is based on distinctive words, fuzzy word similarity, whole-name
    similarity, and numeric consistency.  A single distinctive shared word is
    enough to keep a pair alive for project/AHU matching, while multiple shared
    words raise confidence.  Generic words such as FABRIKA/YENI/YATIRIM are not
    allowed to establish identity on their own.
    """
    try:
        left_n = normalize_project_name(left or "")
        right_n = normalize_project_name(right or "")
        if not left_n or not right_n:
            return 0.0, "NO_MATCH", "missing project name"
        if left_n == right_n:
            return 1.0, "EXACT", "normalized project names are identical"

        left_core = _core_tokens(left_n)
        right_core = _core_tokens(right_n)
        if not left_core or not right_core:
            # Fall back to the whole-name similarity only when both names are
            # short; otherwise generic metadata words are too weak to identify
            # a project safely.
            sequence = SequenceMatcher(None, _compact(left_n), _compact(right_n)).ratio()
            if sequence >= 0.90:
                return round(sequence, 4), "HIGH_CONFIDENCE", "very similar project labels"
            return 0.0, "NO_MATCH", "no distinctive project tokens"

        similarities, matched_left = _match_core_tokens(left_core, right_core)
        matched_count = len(similarities)
        min_core = min(len(left_core), len(right_core))
        max_core = max(len(left_core), len(right_core))
        token_coverage = matched_count / min_core if min_core else 0.0
        jaccard_like = matched_count / (len(left_core) + len(right_core) - matched_count)
        token_quality = sum(similarities) / matched_count if matched_count else 0.0
        sequence = SequenceMatcher(None, _compact(left_n), _compact(right_n)).ratio()

        left_nums = _numeric_tokens(left_n)
        right_nums = _numeric_tokens(right_n)
        numeric_conflict = bool(left_nums and right_nums and left_nums.isdisjoint(right_nums))

        # Exact/fuzzy distinctive words carry the most weight.  Whole-name
        # sequence similarity helps with reordered/truncated labels but cannot
        # override a lack of meaningful common words.
        score = min(
            1.0,
            0.50 * jaccard_like
            + 0.25 * token_coverage
            + 0.10 * token_quality
            + 0.15 * sequence,
        )

        if matched_count == 0:
            # No common identity token: only a very strong complete-name match
            # may survive, otherwise it is genuinely a different project.
            if sequence >= 0.90 and not numeric_conflict:
                return round(sequence, 4), "HIGH_CONFIDENCE", "very similar project labels"
            return round(score, 4), "NO_MATCH", "no matching distinctive project words"

        if numeric_conflict and matched_count < 2:
            return min(round(score, 4), 0.55), "REVIEW_REQUIRED", "shared project word but conflicting numeric identifiers"

        if matched_count >= 2 and token_coverage >= 0.80 and jaccard_like >= 0.60:
            return max(round(score, 4), 0.85), "HIGH_CONFIDENCE", "multiple matching distinctive project words"

        if matched_count >= 2 or token_coverage >= 0.80:
            return max(round(score, 4), 0.60), "MEDIUM_CONFIDENCE", "matching distinctive project words"

        # One distinctive word is intentionally enough to keep the pair as a
        # candidate.  The caller can combine this with AHU overlap; interactive
        # confirmation can also ask the user when the project label is weak.
        return max(round(score, 4), 0.50), "REVIEW_REQUIRED", "shared distinctive project word"
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

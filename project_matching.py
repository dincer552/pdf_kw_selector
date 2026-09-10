"""Safe project-name and identifier matching for multi-PDF workflows."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
import re

from app_logger import debug, exception, info, warning
from project_discovery import ProjectDiscovery, ProjectCandidate, normalize_project_name

_CONTEXT_TOKENS = {"proje", "project", "name", "faz", "phase", "ahu", "unit", "g", "grup", "group", "rev", "revision", "revizyon", "drawing", "elektrik", "uretim", "üretim"}

def _tokens(value: str | None) -> list[str]:
    return [t for t in normalize_project_name(value or "").split() if t]

def _core_tokens(value: str | None) -> set[str]:
    return {t for t in _tokens(value) if t not in _CONTEXT_TOKENS}

def _compact(value: str | None) -> str:
    return "".join(_tokens(value))

def _numeric_tokens(value: str | None) -> set[str]:
    return set(re.findall(r"\d+", normalize_project_name(value or "")))

def _matching_display_name(value: str | None) -> str | None:
    if value is None: return None
    return re.sub(r"^\s*project\s+", "", value, flags=re.I).strip() or value

def _normalized_identifier(value: str | None) -> str:
    value = str(value or "").upper().replace("İ", "I").strip()
    value = re.sub(r"[^A-Z0-9]+", "", value)
    return value

def _identifier_tokens(discovery: ProjectDiscovery) -> set[str]:
    out = set()
    for candidate in discovery.candidates:
        # Candidate itself can contain an order/project number alongside the name.
        out.update(_numeric_tokens(candidate.value))
    return out

def _extract_id_from_text(value: str | None) -> set[str]:
    if not value: return set()
    return set(re.findall(r"(?<![A-Z])\d{5,}(?!\d)", value.upper()))

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

    def to_dict(self) -> dict: return asdict(self)

def score_project_names(left: str | None, right: str | None) -> tuple[float, str, str]:
    try:
        left_n = normalize_project_name(left or ""); right_n = normalize_project_name(right or "")
        if not left_n or not right_n: return 0.0, "NO_MATCH", "missing project name"
        if left_n == right_n: return 1.0, "EXACT", "normalized project names are identical"
        left_core = _core_tokens(left_n); right_core = _core_tokens(right_n)
        if not left_core or not right_core: return 0.0, "NO_MATCH", "no usable core project tokens"
        intersection = left_core & right_core; union = left_core | right_core
        jaccard = len(intersection) / len(union) if union else 0.0
        coverage = len(intersection) / max(1, min(len(left_core), len(right_core)))
        sequence = SequenceMatcher(None, _compact(left_n), _compact(right_n)).ratio()
        left_nums = _numeric_tokens(left_n); right_nums = _numeric_tokens(right_n)
        numeric_conflict = bool(left_nums and right_nums and left_nums.isdisjoint(right_nums))
        score = min(1.0, 0.50*jaccard + 0.35*coverage + 0.15*sequence)
        if numeric_conflict and len(intersection) < 4: return min(score, 0.55), "REVIEW_REQUIRED", "project names share text but numeric identifiers conflict"
        if coverage >= 0.80 and jaccard >= 0.60 and len(intersection) >= 3: return max(score, 0.85), "HIGH_CONFIDENCE", "strong common core project name"
        if coverage >= 0.60 and jaccard >= 0.40: return score, "MEDIUM_CONFIDENCE", "partially matching core project name"
        if score >= 0.45: return score, "REVIEW_REQUIRED", "similar project names require user confirmation"
        return score, "NO_MATCH", "insufficient project-name agreement"
    except Exception as exc:
        exception("Proje eşleşme skoru hesaplama hatası", exc, left=left, right=right); raise

def match_project_names(left: str | None, right: str | None, *, left_source: str | None = None, right_source: str | None = None) -> ProjectMatch:
    score, status, reason = score_project_names(left, right)
    return ProjectMatch(left, right, normalize_project_name(left or "") or None, normalize_project_name(right or "") or None, round(score, 4), status, reason, left_source, right_source)

def _best_candidate(discovery: ProjectDiscovery, target: ProjectDiscovery) -> tuple[ProjectCandidate | None, float, str, str]:
    best_tuple = (None, -1.0, "NO_MATCH", "")
    for left in discovery.candidates or ():
        for right in target.candidates or ():
            score, status, reason = score_project_names(left.value, right.value)
            if score > best_tuple[1]: best_tuple = (right, score, status, reason)
        if best_tuple[0] is not None and best_tuple[1] >= 1.0: break
    return best_tuple

def match_discoveries(left: ProjectDiscovery, right: ProjectDiscovery) -> ProjectMatch:
    try:
        candidate, score, status, reason = _best_candidate(left, right)
        right_raw = candidate.value if candidate else right.project_name
        left_raw = left.project_name
        # Exact/strong textual match first.
        if status not in {"EXACT", "HIGH_CONFIDENCE"}:
            left_display = _matching_display_name(left_raw); right_display = _matching_display_name(right_raw)
        else:
            left_display = left_raw; right_display = right_raw
        result = ProjectMatch(left_display, right_display, left.project_name_normalized, normalize_project_name(right_raw or "") or None, round(max(score, 0.0), 4), status, reason, left.project_source, candidate.source if candidate else right.project_source)
        debug("Discovery nesneleri proje eşleşti", left=left_raw, right=right_raw, score=result.score, status=status, reason=reason)
        return result
    except Exception as exc:
        exception("Project discovery eşleştirme hesaplama hatası", exc, left=left.project_name, right=right.project_name); raise

def match_discoveries_with_identifiers(left: ProjectDiscovery, right: ProjectDiscovery, left_text: str = "", right_text: str = "") -> ProjectMatch:
    """Project match that considers project names plus explicit long numeric identifiers such as order numbers."""
    base = match_discoveries(left, right)
    left_ids = _extract_id_from_text(left_text)
    right_ids = _extract_id_from_text(right_text)
    shared = left_ids & right_ids
    if shared:
        # A shared 5+ digit identifier is a strong confirmation even when names differ completely.
        return ProjectMatch(base.left_name, base.right_name, base.left_normalized, base.right_normalized, 1.0, "IDENTIFIER_MATCH", f"shared project/order identifier: {sorted(shared)}", base.left_source, base.right_source)
    return base

def match_discovery_lists(left_items: list[ProjectDiscovery], right_items: list[ProjectDiscovery]) -> list[ProjectMatch]:
    pairs = []
    for i, left in enumerate(left_items):
        for j, right in enumerate(right_items):
            match = match_discoveries(left, right); pairs.append((match.score, i, j, match))
    output = []; used_left = set(); used_right = set()
    for _, i, j, match in sorted(pairs, reverse=True, key=lambda item: item[0]):
        if i in used_left or j in used_right: continue
        output.append(match); used_left.add(i); used_right.add(j)
    info("Toplu proje eşleştirmesi hesaplandı", pdf1_count=len(left_items), pdf2_count=len(right_items), match_count=len(output))
    return output

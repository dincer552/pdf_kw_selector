from types import SimpleNamespace

import confirmation_workflow as workflow
from ahu_matching import AHUDiscovery, EquipmentOccurrence
from project_discovery import ProjectDiscovery


def _project(name, normalized=None):
    normalized = normalized or name.casefold()
    return ProjectDiscovery(name, normalized, "test", 1, "HIGH", ())


def test_project_confirmation_uses_shared_identity_and_requires_user_approval(monkeypatch):
    left = SimpleNamespace(project=_project("EKER BALIKESIR", "eker balikesir"), path="left.pdf")
    right = SimpleNamespace(project=_project("EKER SÜT ÜRÜNLERİ YENİ FABRİKA YATIRIM", "eker sut urunleri yeni fabrika yatirim"), path="right.pdf")

    monkeypatch.setattr(workflow, "_document_identity_tokens", lambda document: {"26END004"})
    asked = []
    monkeypatch.setattr(workflow, "_ask_project", lambda left_name, right_name, shared: asked.append((left_name, right_name, shared)) or True)

    result = workflow._project_confirmation_plan({"left": [left]}, {"right": [right]})

    assert result == {("eker balikesir", "eker sut urunleri yeni fabrika yatirim")}
    assert asked == [("EKER BALIKESIR", "EKER SÜT ÜRÜNLERİ YENİ FABRİKA YATIRIM", {"26END004"})]


def test_ahu_separator_rule_is_asked_once_then_reused(monkeypatch):
    left = SimpleNamespace(path="left.pdf")
    right = SimpleNamespace(path="right.pdf")

    left_discovery = AHUDiscovery((
        EquipmentOccurrence("AD-AHU-01", "AHU-01", 1, "test"),
        EquipmentOccurrence("AD-AHU-02", "AHU-02", 2, "test"),
    ))
    right_discovery = AHUDiscovery((
        EquipmentOccurrence("AD_AHU_01", "AHU-01", 1, "test"),
        EquipmentOccurrence("AD_AHU_02", "AHU-02", 2, "test"),
    ))
    monkeypatch.setattr(workflow.batch, "discover_equipment", lambda path: left_discovery if path == "left.pdf" else right_discovery)

    asked = []
    monkeypatch.setattr(workflow, "_ask_ahu", lambda project, left_name, right_name, reused_rule=False: asked.append((left_name, right_name, reused_rule)) or True)

    approved, reused = workflow._build_ahu_confirmations([("EKER BALIKESIR", [left], [right])])

    assert len(approved) == 1
    assert len(reused) == 1
    assert len(asked) == 1
    assert asked[0][2] is False


def test_flexible_ahu_key_ignores_separators_and_leading_zeroes():
    assert workflow._flexible_ahu_key("AD-AHU-01") == workflow._flexible_ahu_key("AD_AHU_1")
    assert workflow._flexible_ahu_key("AHU-A-001") == workflow._flexible_ahu_key("AHU_A_1")


def test_flexible_ahu_key_keeps_distinct_suffixes_distinct():
    assert workflow._flexible_ahu_key("AHU-A-1") != workflow._flexible_ahu_key("AHU-A-1A")

from types import SimpleNamespace

from desktop_grouped_app import GroupedApp


class FakeTabs:
    def __init__(self):
        self.labels = {}

    def tab(self, target, text):
        self.labels[target] = text


class FakeTree:
    def get_children(self):
        return ("pdf1-row", "pdf2-row")


class FakeApp(SimpleNamespace):
    def __getattr__(self, name):
        if name.endswith("_tab"):
            return name
        raise AttributeError(name)


def test_unmatched_tab_count_matches_the_rows_shown():
    categories = {
        "DANFOS": set(),
        "Ziehl-Ab. / EBM": set(),
        "VOCLEAN": set(),
        "SYSRECO": set(),
        "EŞLEŞMEYEN": set(),
    }
    app = FakeApp(
        _validate_pdf_accounting=lambda: (True, categories),
        _unmatched_pdf_keys=set(),
        unmatched_tree=FakeTree(),
        tabs=FakeTabs(),
        unmatched_tab_index=lambda: 4,
    )

    GroupedApp._refresh_grouped_tab_counts(app)

    assert app.tabs.labels[4] == "EŞLEŞMEYEN PDF'LER (2)"

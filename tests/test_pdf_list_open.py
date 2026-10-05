from types import SimpleNamespace

from desktop_app import App


class FakeWidget:
    def __init__(self):
        self.options = {}
        self.bindings = {}

    def configure(self, **options):
        self.options.update(options)

    def bind(self, event, callback):
        self.bindings[event] = callback


def test_pdf_list_item_opens_the_selected_pdf():
    widget = FakeWidget()
    opened = []
    app = SimpleNamespace(
        open_pdf_document=lambda *args: opened.append(args)
    )

    App._bind_pdf_open(app, widget, r"C:\PDFs\selection.pdf", "PDF1")

    assert widget.options["cursor"] == "hand2"
    widget.bindings["<Button-1>"](None)
    assert opened == [(r"C:\PDFs\selection.pdf", 1, "PDF1 PDF")]

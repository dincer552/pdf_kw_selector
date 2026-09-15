"""Build metadata embedded in packaged applications."""

# Install PDF-cell behavior before any Tkinter Treeview is created.
import pdf_click_opener  # noqa: F401
import pdf_hover_indicator  # noqa: F401
import status_badges  # noqa: F401
import button_label_fix  # noqa: F401
import ui_polish  # noqa: F401
import voclean_project_selector  # noqa: F401

BUILD_SHA = "development"
BUILD_VERSION = "v0.5.4"

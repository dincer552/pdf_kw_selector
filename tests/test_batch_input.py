from pathlib import Path

from batch_input import discover_pdfs


def test_discover_multiple_files_and_recursive_folder(tmp_path: Path):
    root = tmp_path / "projects"
    nested = root / "sub"
    nested.mkdir(parents=True)
    first = root / "A.pdf"
    second = nested / "B.PDF"
    ignored = nested / "notes.txt"
    first.write_bytes(b"a")
    second.write_bytes(b"bb")
    ignored.write_text("ignore", encoding="utf-8")

    result = discover_pdfs([first, root])

    assert [Path(item.path).name for item in result] == ["A.pdf", "B.PDF"]
    assert result[0].source == "file"
    assert result[1].source == "folder"
    assert result[1].size_bytes == 2


def test_non_recursive_folder_scan(tmp_path: Path):
    root = tmp_path / "root"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / "top.pdf").write_bytes(b"1")
    (nested / "deep.pdf").write_bytes(b"2")

    result = discover_pdfs([root], recursive=False)

    assert [Path(item.path).name for item in result] == ["top.pdf"]


def test_missing_and_non_pdf_inputs_are_ignored(tmp_path: Path):
    txt = tmp_path / "x.txt"
    txt.write_text("x", encoding="utf-8")

    assert discover_pdfs([tmp_path / "missing.pdf", txt]) == []

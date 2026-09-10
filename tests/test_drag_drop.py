from drag_drop import parse_drop_data


class _FakeTk:
    class _Tk:
        @staticmethod
        def splitlist(data):
            return tuple(data)

    tk = _Tk()


def test_parse_drop_data_preserves_multiple_paths():
    root = _FakeTk()
    paths = parse_drop_data(root, [r"C:\PDF A\one.pdf", r"D:\PDF B\two.pdf"])
    assert paths == [r"C:\PDF A\one.pdf", r"D:\PDF B\two.pdf"]


def test_parse_drop_data_empty():
    assert parse_drop_data(_FakeTk(), "") == []

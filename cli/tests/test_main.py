import json

from bookmgr_cli.main import escape_json_controls, print_json, print_table, sanitize


def test_sanitize_strips_terminal_escapes():
    evil = "title\x1b]0;pwned\x07\x1b[2J\x9b31m\x7f‮end"
    out = sanitize(evil)
    for ch in ("\x1b", "\x07", "\x9b", "\x7f", "‮"):
        assert ch not in out
    assert out.startswith("title") and out.endswith("end")


def test_sanitize_keeps_japanese_and_emoji():
    text = "吾輩は猫である 👨‍👩‍👧"
    assert sanitize(text) == text


def test_print_table_sanitizes_cells(capsys):
    print_table([["TITLE"], ["a\x1b[31mb\nc"]])
    out = capsys.readouterr().out
    assert "\x1b" not in out
    assert out.count("\n") == 2  # header line + one row, no injected newline


def test_print_json_escapes_controls_and_stays_valid(capsys):
    value = {"title": "x\x9b31m‮y\x1b", "author": "夏目漱石"}
    print_json(value)
    out = capsys.readouterr().out
    for ch in ("\x1b", "\x9b", "‮"):
        assert ch not in out
    assert json.loads(out) == value


def test_escape_json_controls_keeps_layout_newlines():
    assert escape_json_controls('{\n  "a": 1\n}') == '{\n  "a": 1\n}'

from io import StringIO
from typing import Any, Callable

import pytest

from stub_extractor.extractor import extract


@pytest.fixture
def _run_extract(capsys: Any) -> Callable[[str], str]:
    def f(source: str) -> str:
        target = StringIO()
        extract(StringIO(source), target)
        assert capsys.readouterr().err == ""
        return target.getvalue()

    return f


def test_invalid_file(_run_extract: Callable[[str], str]) -> None:
    with pytest.raises(SyntaxError):
        _run_extract("123INVALID")


def test_empty_file(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("") == ""


def test_ignore_docstrings(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract('''"""Test"""''') == ""


def test_imports(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("""import os""") == "import os\n"
    assert _run_extract("""import os, sys""") == "import os, sys\n"
    assert _run_extract("""import os as so""") == "import os as so\n"


def test_unannotated_functions(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo():\n  pass") == "def foo(): ...\n"
    assert _run_extract("def foo(x):\n  pass") == "def foo(x): ...\n"
    assert _run_extract("def foo(x, y):\n  pass") == "def foo(x, y): ...\n"


def test_argument_annotations(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo(x: str):\n  pass") == "def foo(x: str): ...\n"


def test_return_annotations(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo() -> str:\n  pass") == "def foo() -> str: ...\n"

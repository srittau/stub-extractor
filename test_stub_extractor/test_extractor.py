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
        return target.getvalue().strip()

    return f


def test_invalid_file(_run_extract: Callable[[str], str]) -> None:
    with pytest.raises(SyntaxError):
        _run_extract("123INVALID")


def test_empty_file(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("") == ""


def test_ignore_docstrings(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract('''"""Test"""''') == ""


def test_imports(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("""import os""") == "import os"
    assert _run_extract("""import os, sys""") == "import os, sys"
    assert _run_extract("""import os as so""") == "import os as so"
    assert _run_extract("""import sys.path""") == "import sys.path"


def test_unannotated_functions(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo():\n  pass") == "def foo(): ..."
    assert _run_extract("def foo(x):\n  pass") == "def foo(x): ..."
    assert _run_extract("def foo(x, y):\n  pass") == "def foo(x, y): ..."


def test_argument_annotations(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo(x: str):\n  pass") == "def foo(x: str): ..."


def test_return_annotations(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo() -> str:\n  pass") == "def foo() -> str: ..."


def test_annotation_constants(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo() -> None: pass") == "def foo() -> None: ..."


def test_annotation_subscripts(_run_extract: Callable[[str], str]) -> None:
    assert (
        _run_extract("def foo() -> Optional[None]: pass")
        == "def foo() -> Optional[None]: ..."
    )
    assert (
        _run_extract("def foo() -> Tuple[None, str]: pass")
        == "def foo() -> Tuple[None, str]: ..."
    )


def test_class_statement(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("class Foo: ...") == "class Foo: ..."


def test_ignore_pass_ellipsis_in_classes(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("class Foo: ...") == "class Foo: ..."
    assert _run_extract("class Foo:\n  pass") == "class Foo: ..."
    assert _run_extract("class Foo:\n  pass\n  ...\n  ...\n  pass") == "class Foo: ..."
    assert (
        _run_extract("class Foo:\n  pass\n  ...\n  def bar(self):\n    pass")
        == "class Foo:\n    def bar(self): ..."
    )


def test_methods(_run_extract: Callable[[str], str]) -> None:
    assert (
        _run_extract(
            """
class Foo:
    def bar(self) -> str:
        pass
"""
        )
        == "class Foo:\n    def bar(self) -> str: ..."
    )


def test_decorators(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("@foo\ndef bar(): pass") == "@foo\ndef bar(): ..."

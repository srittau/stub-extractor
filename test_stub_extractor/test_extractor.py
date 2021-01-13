from io import StringIO
from typing import Any, Callable

import pytest

from stub_extractor.extractor import extract
from stub_extractor.generator import generate


@pytest.fixture
def _run_extract(capsys: Any) -> Callable[[str], str]:
    def f(source: str) -> str:
        module = extract(StringIO(source))
        target = StringIO()
        generate(module, target)
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
    assert _run_extract("""import os, sys""") == "import os\nimport sys"
    assert _run_extract("""import os as so""") == "import os as so"
    assert _run_extract("""import sys.path""") == "import sys.path"


def test_import_froms(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("""from os import x""") == "from os import x"
    assert _run_extract("""from os import x, y""") == "from os import x, y"
    assert _run_extract("""from os import x as y""") == "from os import x as y"


def test_group_imports(_run_extract: Callable[[str], str]) -> None:
    assert (
        _run_extract(
            """from os import x\ndef foo(): ...\nimport sys\nfrom itertools import chain"""
        )
        == "import sys\nfrom os import x\nfrom itertools import chain\ndef foo(): ..."
    )


def test_relative_imports(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("""from . import x""") == "from . import x"
    assert _run_extract("""from .os import x""") == "from .os import x"
    assert _run_extract("""from ...os import x""") == "from ...os import x"


def test_type_aliases(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("Alias = str") == "Alias = str"
    assert _run_extract("Alias1 = Alias2 = str") == "Alias1 = str\nAlias2 = str"
    assert (
        _run_extract("from typing import Optional\nAlias = Optional[str]")
        == "from typing import Optional\nAlias = Optional[str]"
    )


def test_top_level_constants(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("x = None") == "x: Optional[Any]"
    assert _run_extract("x = 'foo'") == "x: str"
    assert _run_extract("x = 'int'") == "x: str"
    assert _run_extract("x = b'foo'") == "x: bytes"
    assert _run_extract("x = 3") == "x: int"
    assert _run_extract("x = 3.3") == "x: float"
    assert _run_extract("x = y = ''") == "x: str\ny: str"


def test_top_level_assignments(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("x = []") == "x: List[Any]"
    assert _run_extract("x = {}") == "x: Dict[Any, Any]"
    assert _run_extract("x = {1, 2}") == "x: Set[Any]"
    assert _run_extract("x = (1,)") == "x: Tuple[Any, ...]"
    assert _run_extract("x = foo()") == "x: Any"


def test_top_level_ann_assignments(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("x: int = 123") == "x: int"
    assert _run_extract("x: str") == "x: str"


def test_ignored_top_level(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("x += 3") == ""


def test_unannotated_functions(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo():\n  pass") == "def foo(): ..."
    assert _run_extract("def foo(x):\n  pass") == "def foo(x): ..."
    assert _run_extract("def foo(x, y):\n  pass") == "def foo(x, y): ..."


def test_kw_only_arguments(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo(*, x, y): pass") == "def foo(*, x, y): ..."
    assert _run_extract("def foo(x, *, y): pass") == "def foo(x, *, y): ..."


def test_variable_arguments(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo(*bar): pass") == "def foo(*bar): ..."
    assert _run_extract("def foo(*bar: str): pass") == "def foo(*bar: str): ..."
    assert _run_extract("def foo(abc, *bar): pass") == "def foo(abc, *bar): ..."
    assert _run_extract("def foo(*bar, abc): pass") == "def foo(*bar, abc): ..."


def test_variable_kw_arguments(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo(**bar): pass") == "def foo(**bar): ..."
    assert _run_extract("def foo(**bar: str): pass") == "def foo(**bar: str): ..."
    assert _run_extract("def foo(abc, **bar): pass") == "def foo(abc, **bar): ..."
    assert _run_extract("def foo(*bar, **abc): pass") == "def foo(*bar, **abc): ..."
    assert _run_extract("def foo(*, bar, **abc): pass") == "def foo(*, bar, **abc): ..."


def test_argument_defaults(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo(x=None): pass") == "def foo(x=...): ..."
    assert _run_extract("def foo(x, y=None): pass") == "def foo(x, y=...): ..."
    assert _run_extract("def foo(*, x, y=''): pass") == "def foo(*, x, y=...): ..."
    assert (
        _run_extract("def foo(x: int = 3, *, y: str = ''): pass")
        == "def foo(x: int = ..., *, y: str = ...): ..."
    )


def test_argument_annotations(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo(x: str):\n  pass") == "def foo(x: str): ..."


def test_return_annotations(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo() -> str:\n  pass") == "def foo() -> str: ..."


def test_annotations(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def func() -> foo.bar: pass") == "def func() -> foo.bar: ..."
    assert (
        _run_extract("def func() -> foo.Bar[str]: pass")
        == "def func() -> foo.Bar[str]: ..."
    )


def test_annotation_constants(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo() -> None: pass") == "def foo() -> None: ..."
    assert (
        _run_extract("def foo() -> Tuple[int, ...]: pass")
        == "def foo() -> Tuple[int, ...]: ..."
    )


def test_string_annotations(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("def foo(x: 'X[str]'): pass") == "def foo(x: X[str]): ..."
    assert _run_extract("def foo() -> 'None': pass") == "def foo() -> None: ..."
    assert (
        _run_extract("def foo() -> Optional['None']: pass")
        == "def foo() -> Optional[None]: ..."
    )


def test_annotation_subscripts(_run_extract: Callable[[str], str]) -> None:
    assert (
        _run_extract("def foo() -> Optional[None]: pass")
        == "def foo() -> Optional[None]: ..."
    )
    assert (
        _run_extract("def foo() -> Optional[Type[None]]: pass")
        == "def foo() -> Optional[Type[None]]: ..."
    )
    assert (
        _run_extract("def foo() -> Tuple[None, str]: pass")
        == "def foo() -> Tuple[None, str]: ..."
    )
    assert (
        _run_extract("def foo() -> Callable[[str, bool], None]: pass")
        == "def foo() -> Callable[[str, bool], None]: ..."
    )


def test_class_statement(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("class Foo: ...") == "class Foo: ..."
    assert _run_extract("class Foo(Bar): pass") == "class Foo(Bar): ..."
    assert _run_extract("class Foo(Bar, Baz): pass") == "class Foo(Bar, Baz): ..."
    assert (
        _run_extract("class Foo(Bar[Baz[_T]]): pass") == "class Foo(Bar[Baz[_T]]): ..."
    )
    assert _run_extract("class Foo(bar.Bar): pass") == "class Foo(bar.Bar): ..."
    assert _run_extract("class Foo(X.Bar[Y]): pass") == "class Foo(X.Bar[Y]): ..."
    assert _run_extract("class Foo(Bar[X.Y]): pass") == "class Foo(Bar[X.Y]): ..."
    assert _run_extract("class Foo(Bar[X, Y]): pass") == "class Foo(Bar[X, Y]): ..."


def test_class_keyword(_run_extract: Callable[[str], str]) -> None:
    assert (
        _run_extract("class Foo(metaclass=Bar): pass")
        == "class Foo(metaclass=Bar): ..."
    )
    assert (
        _run_extract("class Foo(Super, metaclass=Bar): pass")
        == "class Foo(Super, metaclass=Bar): ..."
    )


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


def test_class_fields(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("class Foo:\n  x = True") == "class Foo:\n    x: ClassVar[Any]"
    assert (
        _run_extract("class Foo:\n  x = y = True")
        == "class Foo:\n    x: ClassVar[Any]\n    y: ClassVar[Any]"
    )
    assert (
        _run_extract("class Foo:\n  x, y = 1, 2")
        == "class Foo:\n    x: ClassVar[Any]\n    y: ClassVar[Any]"
    )


def test_class_ann_assignments(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("class Foo:\n  x: int = 123") == "class Foo:\n    x: int"
    assert _run_extract("class Foo:\n  x: str") == "class Foo:\n    x: str"


def test_ignored_class_statements(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("class Foo:\n  x += 3") == "class Foo: ..."


def test_decorators(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("@foo\ndef bar(): pass") == "@foo\ndef bar(): ..."
    assert _run_extract("@foo.baz\ndef bar(): pass") == "@foo.baz\ndef bar(): ..."


def test_conditionals(_run_extract: Callable[[str], str]) -> None:
    assert _run_extract("if True:\n  def foo(): pass\n") == "def foo(): ..."
    assert (
        _run_extract("if True:\n  def foo(): pass\nelse:\n  def bar(): pass")
        == "def foo(): ...\ndef bar(): ..."
    )
    assert (
        _run_extract("if True:\n  def foo(): pass\nelif False:\n  def bar(): pass")
        == "def foo(): ...\ndef bar(): ..."
    )
    assert (
        _run_extract(
            "class Foo:\n  if True:\n    def foo(): pass\n  elif False:\n    def bar(): pass"
        )
        == "class Foo:\n    def foo(): ...\n    def bar(): ..."
    )


def test_conditionals_type_checking(_run_extract: Callable[[str], str]) -> None:
    assert (
        _run_extract(
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n  def foo(): pass\nelse:\n  def bar(): pass"
        )
        == "from typing import TYPE_CHECKING\ndef foo(): ..."
    )
    assert (
        _run_extract(
            "from typing import TYPE_CHECKING\nif not TYPE_CHECKING:\n  def foo(): pass\nelse:\n  def bar(): pass"
        )
        == "from typing import TYPE_CHECKING\ndef bar(): ..."
    )
    assert (
        _run_extract(
            "from typing import TYPE_CHECKING\nclass Foo:\n  if TYPE_CHECKING:\n    def foo(): pass\n  else:\n    def bar(): pass"
        )
        == "from typing import TYPE_CHECKING\nclass Foo:\n    def foo(): ..."
    )


def test_try_blocks(_run_extract: Callable[[str], str]) -> None:
    assert (
        _run_extract(
            "try:\n  from sys import platform\nexcept ImportError:\n  platform: int"
        )
        == "from sys import platform"
    )
    assert (
        _run_extract(
            "try:\n  from sys import platform\nexcept ImportError:\n  pass\nelse:\n  def foo(): pass"
        )
        == "from sys import platform\ndef foo(): ..."
    )
    assert (
        _run_extract("try:\n  from sys import platform\nfinally:\n  def foo(): pass")
        == "from sys import platform\ndef foo(): ..."
    )

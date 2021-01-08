"""Abstract syntax tree, optimized for generating stubs.

This tree does not contain any elements that are irrelevant to stubs.
"""

from __future__ import annotations

from typing import Iterable, Optional, Tuple, Union


class DottedName:
    """An identifier, which might contain dots.

    Examples:
      * foo
      * foo.bar
      * foo.bar.baz
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return self.name


class Type:
    # TODO: This should be structured.

    def __init__(self, name: str) -> None:
        self.name = name


class Annotation:
    """A type annotation."""

    # TODO: This should be structured.

    def __init__(self, content: str) -> None:
        self.content = content


class Module:
    def __init__(
        self,
        imports: Iterable[Import] = [],
        import_froms: Iterable[ImportFrom] = [],
        content: Iterable[ModuleContent] = [],
    ) -> None:
        self.imports = list(imports)
        self.import_froms = list(import_froms)
        self.content = list(content)


class Import:
    def __init__(self, name: str, asname: Optional[str]) -> None:
        self.name = name
        self.asname = asname


class ImportFrom:
    def __init__(
        self, module: str, names: Iterable[Tuple[str, Optional[str]]], *, level: int = 0
    ) -> None:
        self.module = module
        self.names = list(names)
        self.level = level


class Attribute:
    def __init__(self, name: str, annotation: Annotation) -> None:
        self.name = name
        self.annotation = annotation


class Alias:
    def __init__(self, name: str, alias: Annotation) -> None:
        self.name = name
        self.alias = alias


class Function:
    """A function or method."""

    def __init__(
        self,
        name: str,
        args: Iterable[Argument] = [],
        var_arg: Optional[Argument] = None,
        kw_args: Iterable[Argument] = [],
        return_annotation: Optional[Annotation] = None,
        decorators: Iterable[Decorator] = [],
    ) -> None:
        self.name = name
        self.args = list(args)
        self.var_arg = var_arg
        self.kw_args = list(kw_args)
        self.return_annotation = return_annotation
        self.decorators = list(decorators)


class Argument:
    """A function or method argument."""

    def __init__(
        self,
        name: str,
        annotation: Optional[Annotation] = None,
        *,
        has_default: bool = False,
    ) -> None:
        self.name = name
        self.annotation = annotation
        self.has_default = has_default


class Class:
    def __init__(
        self,
        name: str,
        bases: Iterable[Type] = [],
        body: Iterable[ClassContent] = [],
    ) -> None:
        self.name = name
        self.bases = list(bases)
        self.body = list(body)


class ClassAssign:
    """An assignment inside a class body."""

    def __init__(self, name: str) -> None:
        self.name = name


class Decorator:
    def __init__(self, name: DottedName) -> None:
        self.name = name


ModuleContent = Union[Attribute, Alias, Function, Class]
ClassContent = Union[ClassAssign, Function]

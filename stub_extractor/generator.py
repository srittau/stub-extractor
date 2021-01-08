"""Generate a stub from an abstract syntax tree."""

from __future__ import annotations

import types
from typing import TYPE_CHECKING, Optional

from .ts_ast import (
    Annotation,
    Argument,
    Class,
    ClassAssign,
    Decorator,
    Function,
    Import,
    ImportFrom,
    Module,
    ModuleAssign,
)

if TYPE_CHECKING:
    from _typeshed import SupportsWrite


class GeneratorContext:
    def __init__(self, target: SupportsWrite[str]) -> None:
        self._target = target
        self._indentation = 0
        self._new_line = True

    def indent(self) -> _IndentationContext:
        self.finish_line()
        self._indentation += 1
        return _IndentationContext(self)

    def unindent(self) -> None:
        self.finish_line()
        assert self._indentation > 0
        self._indentation -= 1

    def write(self, s: str) -> None:
        if self._new_line:
            self._target.write("    " * self._indentation)
            self._new_line = False
        self._target.write(s)

    def finish_line(self, s: str = "") -> None:
        self.write(s)
        self.write("\n")
        self._new_line = True

    def write_line(self, s: str) -> None:
        self.finish_line(s)


class _IndentationContext:
    def __init__(self, context: GeneratorContext) -> None:
        self._context = context

    def __enter__(self) -> None:
        pass

    def __exit__(
        self,
        exc_type: Optional[BaseException],
        exc_value: Optional[BaseException],
        tb: types.TracebackType,
    ) -> None:
        self._context.unindent()


def generate(module: Module, target: SupportsWrite[str]) -> None:
    context = GeneratorContext(target)
    generate_module(module, context)


def generate_annotation(annotation: Annotation, context: GeneratorContext) -> None:
    context.write(annotation.content)


def generate_module(module: Module, context: GeneratorContext) -> None:
    for item in module.content:
        if isinstance(item, Import):
            generate_import(item, context)
        elif isinstance(item, ImportFrom):
            generate_import_from(item, context)
        elif isinstance(item, ModuleAssign):
            generate_module_assign(item, context)
        elif isinstance(item, Function):
            generate_function(item, context)
        elif isinstance(item, Class):
            generate_class(item, context)


def generate_import(imp: Import, context: GeneratorContext) -> None:
    context.write("import ")
    context.write(imp.name)
    if imp.asname:
        context.write(" as ")
        context.write(imp.asname)
    context.finish_line()


def generate_import_from(imp: ImportFrom, context: GeneratorContext) -> None:
    context.write("from ")
    context.write("." * imp.level)
    context.write(imp.module)
    context.write(" import ")
    names = [f"{name} as {asname}" if asname else name for name, asname in imp.names]
    context.write(", ".join(names))
    context.finish_line()


def generate_module_assign(assign: ModuleAssign, context: GeneratorContext) -> None:
    context.write(assign.name)
    context.write(" = ")
    generate_annotation(assign.annotation, context)
    context.finish_line()


def generate_function(function: Function, context: GeneratorContext) -> None:
    for decorator in function.decorators:
        if decorator:
            generate_decorator(decorator, context)
    context.write(f"def {function.name}(")

    first_arg = True
    for ast_arg in function.args:
        if not first_arg:
            context.write(", ")
        generate_argument(ast_arg, context)
        first_arg = False

    if function.kw_args:
        if not first_arg:
            context.write(", ")
        context.write("*")
        first_arg = False
        for ast_arg in function.kw_args:
            context.write(", ")
            generate_argument(ast_arg, context)

    context.write(")")
    if function.return_annotation:
        context.write(" -> ")
        context.write(function.return_annotation.content)
    context.finish_line(": ...")


def generate_argument(argument: Argument, context: GeneratorContext) -> None:
    context.write(argument.name)
    if argument.annotation:
        context.write(": ")
        generate_annotation(argument.annotation, context)
    if argument.has_default:
        context.write(" = ..." if argument.annotation else "=...")


def generate_class(ast_class: Class, context: GeneratorContext) -> None:
    context.write("class ")
    context.write(ast_class.name)
    if ast_class.bases:
        context.write("(")
        context.write(", ".join(b.name for b in ast_class.bases))
        context.write(")")
    context.write(":")
    if len(ast_class.body) == 0:
        context.finish_line(" ...")
    else:
        with context.indent():
            for body_el in ast_class.body:
                if isinstance(body_el, Function):
                    generate_function(body_el, context)
                elif isinstance(body_el, ClassAssign):
                    generate_class_assignment(body_el, context)
                else:
                    raise RuntimeError(
                        f"missing handler for {type(body_el)} in class body"
                    )


def generate_class_assignment(assign: ClassAssign, context: GeneratorContext) -> None:
    context.write(assign.name)
    context.finish_line(": ClassVar[Any]")


def generate_decorator(decorator: Decorator, context: GeneratorContext) -> None:
    context.write("@")
    context.finish_line(str(decorator.name))

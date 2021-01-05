from __future__ import annotations

import ast
import sys
import types
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from _typeshed import SupportsRead, SupportsWrite


class ExtractContext:
    def __init__(self, target: SupportsWrite[str], filename: str) -> None:
        self._target = target
        self.filename = filename
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
        self.write(s)
        self.finish_line()

    def warn(self, msg: str) -> None:
        print(f"WARNING:{self.filename}:{msg}", file=sys.stderr)


class _IndentationContext:
    def __init__(self, context: ExtractContext) -> None:
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


def extract(
    source: SupportsRead[str], target: SupportsWrite[str], filename: str = "<unknown>"
) -> None:
    context = ExtractContext(target, filename)
    tree = ast.parse(source.read(), filename=filename, type_comments=True)
    _extract_module(tree, context)


def _extract_module(module: ast.Module, context: ExtractContext) -> None:
    for child in module.body:
        if isinstance(child, ast.Expr):
            _extract_naked_expr(child, context)
        elif isinstance(child, ast.Import):
            _extract_import(child, context)
        elif isinstance(child, ast.FunctionDef):
            _extract_function(child, context)
        elif isinstance(child, ast.ClassDef):
            _extract_class(child, context)
        else:
            _warn_unsupported_ast(module, child, context)


def _extract_naked_expr(expr: ast.Expr, context: ExtractContext) -> None:
    if isinstance(expr.value, ast.Constant):
        pass  # Ignore constants (e.g. docstrings).
    else:
        _warn_unsupported_ast(expr, expr.value, context)


def _extract_import(import_: ast.Import, context: ExtractContext) -> None:
    # For now, we extract imports verbatim. In the future, imports need to
    # be pruned to imports actually used in the stubs.
    context.write("import ")
    imports = []
    for name in import_.names:
        if name.asname:
            imports.append(f"{name.name} as {name.asname}")
        else:
            imports.append(name.name)
    context.write(", ".join(imports))
    context.finish_line()


def _extract_function(func: ast.FunctionDef, context: ExtractContext) -> None:
    context.write(f"def {func.name}(")
    _extract_argument_list(func, context)
    if func.decorator_list:
        context.warn(f"{func.lineno}:decorators are currently unsupported")
    context.write(")")
    ret_annotation = _get_annotation(func.returns, context)
    if ret_annotation:
        context.write(" -> ")
        context.write(ret_annotation)
    if func.type_comment:
        context.warn(f"{func.lineno}:function type comments are currently unsupported")
    context.finish_line(": ...")
    # The body of functions is ignored.


def _extract_argument_list(func: ast.FunctionDef, context: ExtractContext) -> None:
    args = func.args
    if args.posonlyargs:
        context.warn(f"{func.lineno}:position-only arguments are currently unsupported")
    for i, arg in enumerate(args.args):
        if i > 0:
            context.write(", ")
        _extract_argument(arg, context)
    if args.vararg:
        context.warn(f"{func.lineno}:variable arguments are currently unsupported")
    if args.kwonlyargs:
        context.warn(f"{func.lineno}:keyword-only arguments are currently unsupported")
    if args.kw_defaults:
        context.warn(f"{func.lineno}:argument defaults are currently unsupported")
    if args.kw_defaults:
        context.warn(
            f"{func.lineno}:variable keyword arguments are currently unsupported"
        )
    if args.defaults:
        context.warn(f"{func.lineno}:argument defaults are currently unsupported")


def _extract_argument(arg: ast.arg, context: ExtractContext) -> None:
    context.write(arg.arg)
    annotation = _get_annotation(arg.annotation, context)
    if annotation:
        context.write(": ")
        context.write(annotation)
    if arg.type_comment:
        context.warn(f"{arg.lineno}:argument type comments are currently unsupported")


def _extract_class(klass: ast.ClassDef, context: ExtractContext) -> None:
    if klass.decorator_list:
        context.warn(f"{klass.lineno}:class decorators are currently unsupported")
    context.write("class ")
    context.write(klass.name)
    if klass.bases:
        context.warn(f"{klass.lineno}:base classes are currently unsupported")
    if klass.keywords:
        context.warn(f"{klass.lineno}:class keywords are currently unsupported")
    context.write(":")
    if _is_class_body_empty(klass):
        context.finish_line(" ...")
    else:
        with context.indent():
            _extract_class_body(klass, context)


def _is_class_body_empty(klass: ast.ClassDef) -> bool:
    return all(_is_pass_or_ellipsis(s) for s in klass.body)


def _extract_class_body(klass: ast.ClassDef, context: ExtractContext) -> None:
    for stmt in klass.body:
        if _is_pass_or_ellipsis(stmt):
            pass
        elif isinstance(stmt, ast.FunctionDef):
            _extract_function(stmt, context)
        else:
            context.warn(
                f"{stmt.lineno}:unsupported ast type '{type(stmt).__name__}' in class body"
            )


def _is_pass_or_ellipsis(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Pass)
        or isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
    )


def _get_annotation(
    annotation: Optional[ast.expr], context: ExtractContext
) -> Optional[str]:
    if annotation is None:
        return None
    if isinstance(annotation, ast.Name):
        return annotation.id
    else:
        context.warn(
            f"{annotation.lineno}:unsupported ast type '{type(annotation).__name__}' for annotations"
        )
        return None


def _warn_unsupported_ast(
    parent: ast.AST, child: ast.AST, context: ExtractContext
) -> None:
    context.warn(
        f"{child.lineno}:unsupported ast type '{type(child).__name__}' in '{type(parent).__name__}'"
    )

from __future__ import annotations

import ast
import sys
import types
from typing import TYPE_CHECKING, List, Optional, cast

from .util import rzip_longest

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

    def unsupported(self, obj: ast.AST, what: str) -> None:
        print(
            f"WARNING:{self.filename}:{obj.lineno}:{what} are currently unsupported",
            file=sys.stderr,
        )

    def warn(self, obj: ast.AST, msg: str) -> None:
        print(f"WARNING:{self.filename}:{obj.lineno}:{msg}", file=sys.stderr)


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
    for decorator in func.decorator_list:
        _extract_decorator(decorator, context)
    context.write(f"def {func.name}(")
    _extract_argument_list(func, context)
    context.write(")")
    ret_annotation = _get_annotation(func.returns, context)
    if ret_annotation:
        context.write(" -> ")
        context.write(ret_annotation)
    if func.type_comment:
        context.unsupported(func, "function type comments")
    context.finish_line(": ...")
    # The body of functions is ignored.


def _extract_decorator(decorator: ast.expr, context: ExtractContext) -> None:
    if isinstance(decorator, ast.Name):
        context.write("@")
        context.finish_line(decorator.id)
    else:
        context.warn(
            decorator,
            f"unsupported ast type '{type(decorator).__name__}' for decorators",
        )


def _extract_argument_list(func: ast.FunctionDef, context: ExtractContext) -> None:
    first_arg = True
    if func.args.posonlyargs:
        context.unsupported(func, "position-only arguments")
    assert len(func.args.defaults) <= len(func.args.args)
    for arg, default in rzip_longest(func.args.args, func.args.defaults):
        if not first_arg:
            context.write(", ")
        _extract_argument(arg, default, context)
        first_arg = False
    if func.args.vararg:
        context.unsupported(func, "variable arguments")
    assert len(func.args.kw_defaults) == len(func.args.kwonlyargs)
    if func.args.kwonlyargs:
        if not first_arg:
            context.write(", ")
        context.write("*")
        first_arg = False
        for arg, default in zip(func.args.kwonlyargs, func.args.kw_defaults):
            context.write(", ")
            _extract_argument(arg, default, context)
    if func.args.kwarg:
        context.unsupported(func, "variable keyword arguments")


def _extract_argument(
    arg: ast.arg, default: Optional[ast.expr], context: ExtractContext
) -> None:
    context.write(arg.arg)
    annotation = _get_annotation(arg.annotation, context)
    if annotation:
        context.write(": ")
        context.write(annotation)
    if default is not None:
        context.write(" = ..." if annotation else "=...")
    if arg.type_comment:
        context.unsupported(arg, "argument type comments")


def _extract_class(klass: ast.ClassDef, context: ExtractContext) -> None:
    if klass.decorator_list:
        context.unsupported(klass, "class decorators")
    context.write("class ")
    context.write(klass.name)
    if klass.bases:
        context.unsupported(klass, "base classes")
    if klass.keywords:
        context.unsupported(klass, "class keywords")
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
                stmt, f"unsupported ast type '{type(stmt).__name__}' in class body"
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
    if isinstance(annotation, ast.Constant):
        if annotation.value is None:
            return "None"
        else:
            context.warn(
                annotation,
                f"unsupported constant {annotation.value} for annotations",
            )
            return None
    if isinstance(annotation, ast.Name):
        return annotation.id
    elif isinstance(annotation, ast.Subscript):
        return _get_annotation_subscript(annotation, context)
    else:
        context.warn(
            annotation,
            f"unsupported ast type '{type(annotation).__name__}' for annotations",
        )
        return None


def _get_annotation_subscript(
    subscript: ast.Subscript, context: ExtractContext
) -> Optional[str]:
    if not isinstance(subscript.value, ast.Name):
        _warn_unsupported_ast(subscript, subscript.value, context)
        return None
    slice_: ast.AST
    if isinstance(subscript.slice, ast.Index):  # Python 3.8
        slice_ = subscript.slice.value  # type: ignore
    else:  # Python 3.9+
        slice_ = subscript.slice
    if isinstance(slice_, ast.Tuple):
        subs = [_get_annotation(el, context) for el in slice_.elts]
        if any(s is None for s in subs):
            return None
        sub = ", ".join(cast(List[str], subs))
        return f"{subscript.value.id}[{sub}]"
    elif isinstance(slice_, ast.expr):
        sub2 = _get_annotation(slice_, context)
        if sub2 is None:
            return None
        sub = sub2
        return f"{subscript.value.id}[{sub}]"
    else:
        _warn_unsupported_ast(subscript, slice_, context)
        return None


def _warn_unsupported_ast(
    parent: ast.AST, child: ast.AST, context: ExtractContext
) -> None:
    context.warn(
        child,
        f"unsupported ast type '{type(child).__name__}' in '{type(parent).__name__}'",
    )

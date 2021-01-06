from __future__ import annotations

import ast
import sys
import types
from typing import TYPE_CHECKING, Iterable, List, Optional, Union, cast

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
        self.finish_line(s)

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
        elif isinstance(child, ast.ImportFrom):
            _extract_import_from(child, context)
        elif isinstance(child, ast.Assign):
            _extract_type_alias(child, context)
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
    context.write(_get_import_names(import_.names))
    context.finish_line()


def _extract_import_from(import_: ast.ImportFrom, context: ExtractContext) -> None:
    # For now, we extract imports verbatim. In the future, imports need to
    # be pruned to imports actually used in the stubs.
    context.write("from ")
    context.write("." * import_.level)
    if import_.module is not None:
        context.write(import_.module)
    context.write(" import ")
    context.write(_get_import_names(import_.names))
    context.finish_line()


def _get_import_names(names: Iterable[ast.alias]) -> str:
    return ", ".join(
        f"{name.name} as {name.asname}" if name.asname else name.name for name in names
    )


def _extract_type_alias(alias: ast.Assign, context: ExtractContext) -> None:
    # TODO: recognize non-alias assignments

    if alias.type_comment:
        _warn_type_comments(alias, context)
    value_str = _get_annotation(alias.value, context)
    if value_str is None:
        return
    for target in alias.targets:
        if not isinstance(target, ast.Name):
            _warn_unsupported_ast(alias, target, context)
            continue
        context.write(target.id)
        context.write(" = ")
        context.finish_line(value_str)


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
        _warn_type_comments(func, context)
    context.finish_line(": ...")
    # The body of functions is ignored.


def _extract_decorator(decorator: ast.expr, context: ExtractContext) -> None:
    if isinstance(decorator, (ast.Name, ast.Attribute)):
        name = _get_dotted_name(decorator, context)
        if name is not None:
            context.write("@")
            context.finish_line(name)
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
        _warn_type_comments(arg, context)


def _extract_class(klass: ast.ClassDef, context: ExtractContext) -> None:
    if klass.decorator_list:
        context.unsupported(klass, "class decorators")
    context.write("class ")
    context.write(klass.name)
    bases = []
    if klass.bases:
        for base in klass.bases:
            base_str = _get_base_class(base, context)
            if base_str is not None:
                bases.append(base_str)
    if klass.keywords:
        context.unsupported(klass, "class keywords")
    if bases:
        context.write("(")
        context.write(", ".join(bases))
        context.write(")")
    context.write(":")
    if _is_class_body_empty(klass):
        context.finish_line(" ...")
    else:
        with context.indent():
            _extract_class_body(klass, context)


def _get_base_class(
    base: Union[ast.expr, ast.slice], context: ExtractContext
) -> Optional[str]:
    if isinstance(base, ast.Index):  # Python 3.8
        base = base.value  # type: ignore
    if isinstance(base, (ast.Name, ast.Attribute)):
        return _get_dotted_name(base, context)
    elif isinstance(base, ast.Subscript):
        if not isinstance(base.value, (ast.Name, ast.Attribute)):
            _warn_unsupported_ast(base, base.value, context)
            return None
        base_s = _get_dotted_name(base.value, context)
        sub = _get_base_class(base.slice, context)
        if base_s is None or sub is None:
            return None
        return f"{base_s}[{sub}]"
    else:
        context.warn(base, f"unsupported base class type '{type(base).__name__}'")
        return None


def _is_class_body_empty(klass: ast.ClassDef) -> bool:
    return all(_is_pass_or_ellipsis(s) for s in klass.body)


def _extract_class_body(klass: ast.ClassDef, context: ExtractContext) -> None:
    for stmt in klass.body:
        if _is_pass_or_ellipsis(stmt):
            pass
        elif isinstance(stmt, ast.FunctionDef):
            _extract_function(stmt, context)
        elif isinstance(stmt, ast.Assign):
            _extract_class_assign(stmt, context)
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


def _extract_class_assign(assign: ast.Assign, context: ExtractContext) -> None:
    # TODO: make sure that ClassVar and Any are imported
    # TODO: recognize type aliases

    def extract_target(expr: ast.AST) -> None:
        if isinstance(expr, ast.Name):
            context.write(expr.id)
            context.finish_line(": ClassVar[Any]")
        elif isinstance(expr, ast.Tuple):
            for el in expr.elts:
                extract_target(el)
        else:
            _warn_unsupported_ast(target, assign, context)

    if assign.type_comment is not None:
        _warn_type_comments(assign, context)
    for target in assign.targets:
        extract_target(target)


def _get_annotation(
    annotation: Optional[ast.expr], context: ExtractContext
) -> Optional[str]:
    if annotation is None:
        return None
    if isinstance(annotation, ast.Constant):
        if annotation.value is None:
            return "None"
        elif isinstance(annotation.value, str):
            return annotation.value
        else:
            context.warn(
                annotation,
                f"unsupported constant {annotation.value} for annotations",
            )
            return None
    elif isinstance(annotation, (ast.Name, ast.Attribute)):
        return _get_dotted_name(annotation, context)
    elif isinstance(annotation, ast.Subscript):
        return _get_annotation_subscript(annotation, context)
    elif isinstance(annotation, ast.List):
        items = []
        for el in annotation.elts:
            s = _get_annotation(el, context)
            if s:
                items.append(s)
        return f"[{', '.join(items)}]"
    else:
        context.warn(
            annotation,
            f"unsupported ast type '{type(annotation).__name__}' for annotations",
        )
        return None


def _get_dotted_name(obj: ast.expr, context: ExtractContext) -> Optional[str]:
    if isinstance(obj, ast.Name):
        return obj.id
    elif isinstance(obj, ast.Attribute):
        part = _get_dotted_name(obj.value, context)
        if part is None:
            return None
        return f"{part}.{obj.attr}"
        print(obj.value, obj.attr)
    else:
        context.warn(
            obj, f"unsupported ast type for quoted names '{type(obj).__name__}'"
        )
        return None


def _get_annotation_subscript(
    subscript: ast.Subscript, context: ExtractContext
) -> Optional[str]:
    if not isinstance(subscript.value, (ast.Name, ast.Attribute)):
        _warn_unsupported_ast(subscript, subscript.value, context)
        return None
    slice_: ast.AST
    if isinstance(subscript.slice, ast.Index):  # Python 3.8
        slice_ = subscript.slice.value  # type: ignore
    else:  # Python 3.9+
        slice_ = subscript.slice
    value = _get_dotted_name(subscript.value, context)
    if value is None:
        return None
    if isinstance(slice_, ast.Tuple):
        subs = [_get_annotation(el, context) for el in slice_.elts]
        if any(s is None for s in subs):
            return None
        sub = ", ".join(cast(List[str], subs))
        return f"{value}[{sub}]"
    elif isinstance(slice_, ast.expr):
        sub2 = _get_annotation(slice_, context)
        if sub2 is None:
            return None
        sub = sub2
        return f"{value}[{sub}]"
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


def _warn_type_comments(node: ast.AST, context: ExtractContext) -> None:
    context.unsupported(node, "function type comments")

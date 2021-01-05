from __future__ import annotations

import ast
import sys
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from _typeshed import SupportsRead, SupportsWrite


class ExtractContext:
    def __init__(self, target: SupportsWrite[str]) -> None:
        self._target = target

    def write(self, s: str) -> None:
        self._target.write(s)

    def finish_line(self, s: str = "") -> None:
        self._target.write(s)
        self._target.write("\n")

    def write_line(self, s: str) -> None:
        self.write(s)
        self.finish_line()


def extract(source: SupportsRead[str], target: SupportsWrite[str]) -> None:
    context = ExtractContext(target)
    tree = ast.parse(source.read(), type_comments=True)
    _extract_module(tree, context)


def _extract_module(module: ast.Module, context: ExtractContext) -> None:
    for child in module.body:
        pass
        if isinstance(child, ast.Expr):
            _extract_naked_expr(child, context)
        elif isinstance(child, ast.Import):
            _extract_import(child, context)
        elif isinstance(child, ast.FunctionDef):
            _extract_function(child, context)
        else:
            _warn_unsupported_ast(module, child)


def _extract_naked_expr(expr: ast.Expr, context: ExtractContext) -> None:
    if isinstance(expr.value, ast.Constant):
        pass  # Ignore constants (e.g. docstrings).
    else:
        _warn_unsupported_ast(expr, expr.value)


def _extract_import(import_: ast.Import, context: ExtractContext):
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
    _extract_argument_list(func.args, context)
    if func.decorator_list:
        print("WARNING: decorators are currently unsupported", file=sys.stderr)
    context.write(")")
    ret_annotation = _get_annotation(func.returns)
    if ret_annotation:
        context.write(" -> ")
        context.write(ret_annotation)
    if func.type_comment:
        print(
            "WARNING: function type comments are currently unsupported", file=sys.stderr
        )
    context.finish_line(": ...")
    # The body of functions is ignored.


def _extract_argument_list(args: ast.arguments, context: ExtractContext) -> None:
    if args.posonlyargs:
        print(
            "WARNING: position-only arguments are currently unsupported",
            file=sys.stderr,
        )
    for i, arg in enumerate(args.args):
        if i > 0:
            context.write(", ")
        _extract_argument(arg, context)
    if args.vararg:
        print(
            "WARNING: variable arguments are currently unsupported",
            file=sys.stderr,
        )
    if args.kwonlyargs:
        print(
            "WARNING: keyword-only arguments are currently unsupported",
            file=sys.stderr,
        )
    if args.kw_defaults:
        print(
            "WARNING: argument defaults are currently unsupported",
            file=sys.stderr,
        )
    if args.kw_defaults:
        print(
            "WARNING: variable keyword arguments are currently unsupported",
            file=sys.stderr,
        )
    if args.defaults:
        print(
            "WARNING: argument defaults are currently unsupported",
            file=sys.stderr,
        )


def _extract_argument(arg: ast.arg, context: ExtractContext) -> None:
    context.write(arg.arg)
    annotation = _get_annotation(arg.annotation)
    if annotation:
        context.write(": ")
        context.write(annotation)
    if arg.type_comment:
        print(
            "WARNING: argument type comments are currently unsupported",
            file=sys.stderr,
        )


def _get_annotation(annotation: Optional[ast.expr]) -> Optional[str]:
    if annotation is None:
        return None
    if isinstance(annotation, ast.Name):
        return annotation.id
    else:
        print(
            f"WARNING: unsupported ast type '{type(annotation).__name__}' for annotations",
            file=sys.stderr,
        )
        return None


def _warn_unsupported_ast(parent: ast.AST, child: ast.AST) -> None:
    print(
        f"WARNING: unsupported ast type '{type(child).__name__}' in '{type(parent).__name__}'",
        file=sys.stderr,
    )

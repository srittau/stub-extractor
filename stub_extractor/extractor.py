"""Extract a type stub syntax tree from a Python file."""

from __future__ import annotations

import ast
import itertools
import sys
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple, Union

from .ts_ast import (
    Annotation,
    Argument,
    Class,
    ClassAssign,
    ClassContent,
    Decorator,
    DottedName,
    Function,
    Import,
    ImportFrom,
    Module,
    ModuleAssign,
    ModuleContent,
    Type,
)
from .util import rzip_longest

if TYPE_CHECKING:
    from _typeshed import SupportsRead


class ExtractContext:
    def __init__(self, filename: str) -> None:
        self.filename = filename

    def unsupported(self, obj: ast.AST, what: str) -> None:
        print(
            f"WARNING:{self.filename}:{obj.lineno}:{what} are currently unsupported",
            file=sys.stderr,
        )

    def warn(self, obj: ast.AST, msg: str) -> None:
        print(f"WARNING:{self.filename}:{obj.lineno}:{msg}", file=sys.stderr)


def extract(source: SupportsRead[str], filename: str = "<unknown>") -> Module:
    context = ExtractContext(filename)
    tree = ast.parse(source.read(), filename=filename, type_comments=True)
    content = _extract_top_level(tree.body, context)
    return Module(content)


def _extract_top_level(
    body: Iterable[ast.stmt], context: ExtractContext
) -> List[ModuleContent]:
    ast_body: List[ModuleContent] = []
    for child in body:
        if isinstance(child, ast.Expr):
            _extract_naked_expr(child, context)
        elif isinstance(child, ast.Import):
            imp = _extract_import(child, context)
            ast_body.append(imp)
        elif isinstance(child, ast.ImportFrom):
            imp_f = _extract_import_from(child, context)
            ast_body.append(imp_f)
        elif isinstance(child, ast.Assign):
            assigns = _extract_type_alias(child, context)
            ast_body.extend(assigns)
        elif isinstance(child, ast.FunctionDef):
            function = _extract_function(child, context)
            ast_body.append(function)
        elif isinstance(child, ast.ClassDef):
            klass = _extract_class(child, context)
            ast_body.append(klass)
        elif isinstance(child, ast.If):
            ast_body.extend(_extract_top_level_conditional(child, context))
        else:
            context.warn(
                child,
                f"unsupported ast type '{type(child).__name__}' at top-level",
            )
    return ast_body


def _extract_top_level_conditional(
    conditional: ast.If, context: ExtractContext
) -> List[ModuleContent]:
    if _is_type_checking(conditional.test, context):
        return _extract_top_level(conditional.body, context)
    elif _is_inverted_type_checking(conditional.test, context):
        return _extract_top_level(conditional.orelse, context)
    else:
        content1 = _extract_top_level(conditional.body, context)
        content2 = _extract_top_level(conditional.orelse, context)
        return content1 + content2


def _extract_naked_expr(expr: ast.Expr, context: ExtractContext) -> None:
    if isinstance(expr.value, ast.Constant):
        pass  # Ignore constants (e.g. docstrings).
    else:
        _warn_unsupported_ast(expr, expr.value, context)


def _extract_import(import_: ast.Import, context: ExtractContext) -> Import:
    # For now, we extract imports verbatim. In the future, imports need to
    # be pruned to imports actually used in the stubs.
    # TODO: one Import per name
    names = _get_import_names(import_.names)
    return Import(names)


def _extract_import_from(
    import_: ast.ImportFrom, context: ExtractContext
) -> ImportFrom:
    # For now, we extract imports verbatim. In the future, imports need to
    # be pruned to imports actually used in the stubs.
    names = _get_import_names(import_.names)
    return ImportFrom(import_.module or "", names, level=import_.level)


def _get_import_names(aliases: Iterable[ast.alias]) -> List[Tuple[str, Optional[str]]]:
    return [(name.name, name.asname) for name in aliases]


def _extract_type_alias(
    alias: ast.Assign, context: ExtractContext
) -> List[ModuleAssign]:
    # TODO: recognize non-alias assignments

    if alias.type_comment:
        _warn_type_comments(alias, context)
    annotation = _extract_annotation(alias.value, context)
    if annotation is None:
        return []
    assigns = []
    for target in alias.targets:
        if not isinstance(target, ast.Name):
            _warn_unsupported_ast(alias, target, context)
            continue
        assigns.append(ModuleAssign(target.id, annotation))
    return assigns


def _extract_function(func: ast.FunctionDef, context: ExtractContext) -> Function:
    decorators = [_extract_decorator(d, context) for d in func.decorator_list]
    filtered_decorators: List[Decorator] = [d for d in decorators if d]
    ast_args, ast_kwargs = _extract_argument_list(func, context)
    ret_annotation = _extract_annotation(func.returns, context)
    if func.type_comment:
        _warn_type_comments(func, context)
    # The body of functions is ignored.
    return Function(
        func.name, ast_args, ast_kwargs, ret_annotation, filtered_decorators
    )


def _extract_decorator(
    decorator: ast.expr, context: ExtractContext
) -> Optional[Decorator]:
    if isinstance(decorator, (ast.Name, ast.Attribute)):
        name = _extract_dotted_name(decorator, context)
        return Decorator(name) if name else None
    else:
        context.warn(
            decorator,
            f"unsupported ast type '{type(decorator).__name__}' for decorators",
        )
        return None


# Returns (args, kwonly).
def _extract_argument_list(
    func: ast.FunctionDef, context: ExtractContext
) -> Tuple[List[Argument], List[Argument]]:
    if func.args.posonlyargs:
        context.unsupported(func, "position-only arguments")
    assert len(func.args.defaults) <= len(func.args.args)
    ast_args = []
    for arg, default in rzip_longest(func.args.args, func.args.defaults):
        ast_arg = _extract_argument(arg, default, context)
        ast_args.append(ast_arg)
    if func.args.vararg:
        context.unsupported(func, "variable arguments")
    assert len(func.args.kw_defaults) == len(func.args.kwonlyargs)
    ast_kwargs = []
    if func.args.kwonlyargs:
        for arg, default in zip(func.args.kwonlyargs, func.args.kw_defaults):
            ast_arg = _extract_argument(arg, default, context)
            ast_kwargs.append(ast_arg)
    if func.args.kwarg:
        context.unsupported(func, "variable keyword arguments")
    return ast_args, ast_kwargs


def _extract_argument(
    arg: ast.arg, default: Optional[ast.expr], context: ExtractContext
) -> Argument:
    annotation = _extract_annotation(arg.annotation, context)
    if arg.type_comment:
        _warn_type_comments(arg, context)
    return Argument(arg.arg, annotation, has_default=default is not None)


def _extract_class(klass: ast.ClassDef, context: ExtractContext) -> Class:
    if klass.decorator_list:
        context.unsupported(klass, "class decorators")
    base_types = []
    if klass.bases:
        for base in klass.bases:
            base_type = _extract_type(base, context)
            if base_type is not None:
                base_types.append(base_type)
    if klass.keywords:
        context.unsupported(klass, "class keywords")
    body = _extract_class_body(klass.body, context)
    return Class(klass.name, base_types, body)


def _extract_type(
    base: Union[ast.expr, ast.slice], context: ExtractContext
) -> Optional[Type]:
    if isinstance(base, ast.Index):  # Python 3.8
        base = base.value  # type: ignore
    if isinstance(base, (ast.Name, ast.Attribute)):
        name = _extract_dotted_name(base, context)
        if name is None:
            return None
        return Type(name.name)
    elif isinstance(base, ast.Subscript):
        if not isinstance(base.value, (ast.Name, ast.Attribute)):
            _warn_unsupported_ast(base, base.value, context)
            return None
        base_s = _extract_dotted_name(base.value, context)
        sub = _extract_type(base.slice, context)
        if base_s is None or sub is None:
            return None
        return Type(f"{base_s.name}[{sub.name}]")
    else:
        context.warn(base, f"unsupported base class type '{type(base).__name__}'")
        return None


def _extract_class_body(
    cls_body: Iterable[ast.stmt], context: ExtractContext
) -> List[ClassContent]:
    body: List[ClassContent] = []
    for stmt in cls_body:
        if _is_pass_or_ellipsis(stmt):
            pass
        elif isinstance(stmt, ast.FunctionDef):
            method = _extract_function(stmt, context)
            body.append(method)
        elif isinstance(stmt, ast.Assign):
            assigns = _extract_class_assign(stmt, context)
            body.extend(assigns)
        elif isinstance(stmt, ast.If):
            body.extend(_extract_class_conditional(stmt, context))
        else:
            context.warn(
                stmt, f"unsupported ast type '{type(stmt).__name__}' in class body"
            )
    return body


def _extract_class_conditional(
    conditional: ast.If, context: ExtractContext
) -> List[ClassContent]:
    if _is_type_checking(conditional.test, context):
        return _extract_class_body(conditional.body, context)
    elif _is_inverted_type_checking(conditional.test, context):
        return _extract_class_body(conditional.orelse, context)
    else:
        content1 = _extract_class_body(conditional.body, context)
        content2 = _extract_class_body(conditional.orelse, context)
        return content1 + content2


def _is_pass_or_ellipsis(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Pass)
        or isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
    )


def _extract_class_assign(
    assign: ast.Assign, context: ExtractContext
) -> List[ClassAssign]:
    # TODO: make sure that ClassVar and Any are imported
    # TODO: recognize type aliases

    def extract_target(expr: ast.AST) -> List[ClassAssign]:
        if isinstance(expr, ast.Name):
            return [ClassAssign(expr.id)]
        elif isinstance(expr, ast.Tuple):
            return list(
                itertools.chain.from_iterable(extract_target(el) for el in expr.elts)
            )
        else:
            _warn_unsupported_ast(expr, assign, context)
            return []

    if assign.type_comment is not None:
        _warn_type_comments(assign, context)
    return list(
        itertools.chain.from_iterable(extract_target(t) for t in assign.targets)
    )


def _is_type_checking(test: ast.expr, context: ExtractContext) -> bool:
    return _is_qualified_name(test, "typing.TYPE_CHECKING", context)


def _is_inverted_type_checking(test: ast.expr, context: ExtractContext) -> bool:
    if not isinstance(test, ast.UnaryOp) or not isinstance(test.op, ast.Not):
        return False
    return _is_qualified_name(test.operand, "typing.TYPE_CHECKING", context)


def _is_qualified_name(test: ast.expr, name: str, context: ExtractContext) -> bool:
    # TODO: Current this uses a heuristic of well-known names. To implement
    # this properly, we should record known names with their "proper" name
    # in ExtractContext and compare the local name to that.
    if not name.startswith("typing."):
        return False
    if not isinstance(test, ast.Name):
        return False
    return name == f"typing.{test.id}"


def _extract_annotation(
    annotation: Optional[ast.expr], context: ExtractContext
) -> Optional[Annotation]:
    if annotation is None:
        return None
    if isinstance(annotation, ast.Constant):
        if annotation.value is None:
            ast_ann = Annotation("None")
            return ast_ann
        elif isinstance(annotation.value, str):
            ast_ann = Annotation(annotation.value)
            return ast_ann
        else:
            context.warn(
                annotation,
                f"unsupported constant {annotation.value} for annotations",
            )
            return None
    elif isinstance(annotation, (ast.Name, ast.Attribute)):
        name = _extract_dotted_name(annotation, context)
        if name is None:
            return None
        ast_ann = Annotation(name.name)
        return ast_ann
    elif isinstance(annotation, ast.Subscript):
        sub = _get_annotation_subscript(annotation, context)
        if sub is None:
            return None
        ast_ann = Annotation(sub)
        return ast_ann
    elif isinstance(annotation, ast.List):
        items = []
        for el in annotation.elts:
            s = _extract_annotation(el, context)
            if s:
                items.append(s.content)
        ast_ann = Annotation(f"[{', '.join(items)}]")
        return ast_ann
    else:
        context.warn(
            annotation,
            f"unsupported ast type '{type(annotation).__name__}' for annotations",
        )
        return None


def _extract_dotted_name(
    obj: ast.expr, context: ExtractContext
) -> Optional[DottedName]:
    def _get_name(o: ast.expr) -> Optional[str]:
        if isinstance(o, ast.Name):
            return o.id
        elif isinstance(o, ast.Attribute):
            part = _get_name(o.value)
            if part is None:
                return None
            return f"{part}.{o.attr}"
        else:
            context.warn(
                o, f"unsupported ast type for quoted names '{type(obj).__name__}'"
            )
            return None

    name = _get_name(obj)
    return DottedName(name) if name else None


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
    value = _extract_dotted_name(subscript.value, context)
    if value is None:
        return None
    if isinstance(slice_, ast.Tuple):
        subs = [_extract_annotation(el, context) for el in slice_.elts]
        if any(s is None for s in subs):
            return None
        sub = ", ".join(s.content for s in subs if s is not None)
        return f"{value}[{sub}]"
    elif isinstance(slice_, ast.expr):
        sub2 = _extract_annotation(slice_, context)
        if sub2 is None:
            return None
        return f"{value}[{sub2.content}]"
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

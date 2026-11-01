"""AST-backed admission for the owned Python carriers, not a general verifier.

The reference is selected by the receiver from the frozen task registry. No
candidate code runs. A successful result proves erasure of a restricted inert
prefix, relative to ordinary result-only execution on the declared builtin
input domains. It does not certify source provenance, external systems,
resource/trace equivalence, or arbitrary Python observational equivalence.
"""
from __future__ import annotations
import ast
import copy
import io
import re
import tokenize

from .tasks import TASK_BY_NAME

MARKER = re.compile(r'# WM_SITE ([0-9]{2}) (LEXICAL|STRUCTURAL)\Z')
LEXICAL = re.compile(r'(?:wm_bit_([0-9]{2})|wmBit([0-9]{2}))\Z')
LOOP = re.compile(r'_wm_([0-9]{2})\Z')


class AdmissionError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise AdmissionError(message)


def syntax(node):
    return ast.dump(node, include_attributes=False)


def reference(task):
    need(type(task) is str and task in TASK_BY_NAME, 'unknown receiver task')
    tree = ast.parse(TASK_BY_NAME[task].python_reference.replace('__CARRIERS__', ''))
    need(len(tree.body) == 1 and type(tree.body[0]) is ast.FunctionDef,
         'reference must contain one ordinary function')
    # The theorem excludes reflective or frame-sensitive function observations.
    # This guard is intentionally stronger than needed for the frozen registry.
    forbidden = {'locals', 'globals', 'vars', 'dir', 'eval', 'exec', 'getattr',
                 'setattr', 'delattr', 'inspect', 'sys', '__builtins__'}
    need(not any(isinstance(n, ast.Name) and n.id in forbidden for n in ast.walk(tree)),
         'reflective reference is outside result-only admission')
    need(not any(isinstance(n, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal,
                                ast.Yield, ast.YieldFrom, ast.Await)) for n in ast.walk(tree)),
         'effectful reference is outside prefix erasure')
    return tree


def admit_python(task, source):
    """Return actual indexed bits only after syntax and erasure admission.

    Markers are real comment tokens immediately preceding a carrier statement,
    not regex matches inside strings. Full module/function structure and the
    complete remaining function body must equal the receiver's reference AST.
    """
    need(type(source) is str and len(source.encode('utf-8')) <= 65536,
         'source byte bound or type')
    try:
        tree = ast.parse(source)
        # Parsing alone admits some invalid bindings (for example duplicate
        # arguments); compilation is nonexecuting and rejects those as well.
        compile(tree, '<source-admission>', 'exec')
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (SyntaxError, ValueError, tokenize.TokenError, IndentationError) as exc:
        raise AdmissionError('source does not parse and compile') from exc
    base = reference(task)
    need(len(tree.body) == 1 and type(tree.body[0]) is ast.FunctionDef,
         'candidate must contain exactly the reference function')
    fn, ref = tree.body[0], base.body[0]
    count = len(fn.body) - len(ref.body)
    need(0 <= count <= 24, 'carrier prefix size')
    prefix = fn.body[:count]
    erased = copy.deepcopy(tree)
    erased.body[0].body = erased.body[0].body[count:]
    need(syntax(erased) == syntax(base), 'functional body or function interface changed')
    names = {n.id for n in ast.walk(base) if isinstance(n, ast.Name)}
    names.update(n.arg for n in ast.walk(base) if isinstance(n, ast.arg))
    markers = {}
    marker_tokens = []
    for token in tokens:
        if token.type == tokenize.COMMENT and token.string.startswith('# WM_SITE'):
            m = MARKER.fullmatch(token.string)
            need(m is not None, 'invalid marker comment')
            marker_tokens.append(token)
            markers[token.start[0]] = (int(m[1]), m[2].lower(), token.start[1])
    need(len(marker_tokens) == count, 'orphan or missing carrier marker')
    used, observed, previous = set(), {}, -1
    for node in prefix:
        marker = markers.get(node.lineno - 1)
        need(marker is not None, 'marker is not immediately before carrier syntax')
        index, channel, column = marker
        need(column == node.col_offset and previous < index < 24,
             'carrier order, indentation or index')
        previous = index
        if channel == 'lexical':
            need(type(node) is ast.Assign and len(node.targets) == 1
                 and type(node.targets[0]) is ast.Name and type(node.value) is ast.Constant
                 and type(node.value.value) is int and node.value.value == 0,
                 'lexical carrier must be an inert zero assignment')
            name = node.targets[0].id
            m = LEXICAL.fullmatch(name)
            need(m is not None and int(m[1] or m[2]) == index,
                 'lexical name and marker disagree')
            bit = int(m[2] is not None)
        elif type(node) is ast.If:
            need(type(node.test) is ast.Constant and node.test.value is False
                 and len(node.body) == 1 and type(node.body[0]) is ast.Pass
                 and not node.orelse, 'structural carrier must be a false pass')
            name, bit = None, 0
        else:
            need(type(node) is ast.For and type(node.target) is ast.Name
                 and type(node.iter) is ast.Tuple and not node.iter.elts
                 and len(node.body) == 1 and type(node.body[0]) is ast.Pass
                 and not node.orelse, 'structural carrier must be an empty tuple loop')
            name, bit = node.target.id, 1
            m = LOOP.fullmatch(name)
            need(m is not None and int(m[1]) == index, 'loop name and marker disagree')
        if name is not None:
            need(name not in names and name not in used, 'carrier local is not fresh')
            used.add(name)
        observed[index] = bit
    return dict(observed=observed, admitted=True, erased_prefix_statements=count,
                basis='receiver-reference AST identity after restricted inert-prefix erasure',
                semantic_contract='result-only builtin-domain execution without frame/reflection observation')

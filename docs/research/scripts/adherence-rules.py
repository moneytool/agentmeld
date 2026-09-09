"""Rules whose compliance can be checked by a program, not an opinion."""
import ast, re

def _src(code):
    try: return ast.parse(code)
    except SyntaxError: return None

CHECKS = {}
def check(rule_id, text):
    def deco(fn):
        CHECKS[rule_id] = {"text": text, "fn": fn}
        return fn
    return deco

@check("pathlib", "Use `pathlib` for filesystem paths. Never import or use `os.path`.")
def _pathlib(code):
    return "os.path" not in code

@check("no-print", "Never use `print()` for output. Use the `logging` module.")
def _noprint(code):
    t=_src(code)
    if t is None: return None
    return not any(isinstance(n, ast.Call) and getattr(n.func,"id",None)=="print"
                   for n in ast.walk(t))

@check("docstrings", "Every function and class must have a docstring.")
def _docs(code):
    t=_src(code)
    if t is None: return None
    defs=[n for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
    return bool(defs) and all(ast.get_docstring(d) for d in defs)

@check("annotations", "Annotate the parameters and return type of every function.")
def _ann(code):
    t=_src(code)
    if t is None: return None
    fns=[n for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    if not fns: return None
    return all(f.returns is not None and all(a.annotation for a in f.args.args if a.arg!="self")
               for f in fns)

@check("no-bare-except", "Never write a bare `except:`. Always name the exception type.")
def _bare(code):
    t=_src(code)
    if t is None: return None
    return not any(isinstance(n,ast.ExceptHandler) and n.type is None for n in ast.walk(t))

@check("fstrings", "Use f-strings for interpolation. Never use `%` formatting or `.format()`.")
def _fstr(code):
    return ".format(" not in code

@check("british", "Use British spelling in comments and docstrings: colour, behaviour, initialise.")
def _brit(code):
    prose=[]
    for line in code.split("\n"):
        if "#" in line: prose.append(line.split("#",1)[1])
    t=_src(code)
    if t is not None:
        for n in ast.walk(t):
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.Module)):
                d=ast.get_docstring(n)
                if d: prose.append(d)
    blob=" ".join(prose)
    if not blob.strip(): return None
    return not re.search(r"\b(color|behavior|initialize|analyze|organize)\w*", blob, re.I)

@check("no-mutable-default", "Never use a mutable default argument.")
def _mut(code):
    t=_src(code)
    if t is None: return None
    fns=[n for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    return not any(isinstance(d,(ast.List,ast.Dict,ast.Set)) for f in fns for d in f.args.defaults)

def _is_literal(node):
    """A constant declaration binds a literal, not the result of a call."""
    if isinstance(node, ast.Constant): return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_literal(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(_is_literal(k) for k in node.keys if k is not None) and \
               all(_is_literal(v) for v in node.values)
    if isinstance(node, ast.UnaryOp): return _is_literal(node.operand)
    return False

@check("constants-upper", "Module-level constants must be UPPER_SNAKE_CASE.")
def _const(code):
    t=_src(code)
    if t is None: return None
    names=[tg.id for n in t.body if isinstance(n,ast.Assign) and _is_literal(n.value)
           for tg in n.targets if isinstance(tg,ast.Name)]
    if not names: return None
    return all(n.isupper() or n.startswith("_") for n in names)

@check("explicit-encoding", "Always pass `encoding=` explicitly when opening a text file.")
def _enc(code):
    opens=[o for o in re.findall(r"\bopen\s*\(([^)]*)\)", code)
           if not re.search(r"[\"']\w*b\w*[\"']", o)]   # binary mode takes no encoding
    if not opens: return None
    return all("encoding" in o for o in opens)

FILLER = [
    "Prefer composition over inheritance where both are reasonable.",
    "Keep functions under 40 lines where practical.",
    "Name booleans with an `is_` or `has_` prefix.",
    "Avoid abbreviations in identifiers except for well-known ones.",
    "Group imports: standard library, third party, local.",
    "Raise specific exception subclasses rather than generic ones.",
    "Do not catch an exception you cannot handle meaningfully.",
    "Return early to reduce nesting.",
    "Prefer immutable data structures where practical.",
    "Document non-obvious algorithmic choices with a short comment.",
]

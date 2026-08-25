# AUTO-SPLIT from tr0ngx_obfuscator.py (mechanical slice, imports pending repair)
# ═══════════════════════════════════════════════════════════════
# TR0NGX TRUE VIRTUAL MACHINE (TVM 2.0) HIGH-ASSURANCE ENGINE
# Translates Python AST into Custom ISA Bytecode and executes via
# a Polymorphic Frame-Based Virtual Machine Interpreter.
# 100% Zero-exec fallback: FunctionDef, ClassDef, Try/Except,
# Loops, Closures, and Slices are fully virtualized.
# ═══════════════════════════════════════════════════════════════
import ast
import random
import secrets
import marshal
import hashlib
import hmac
import os

from typing import Any, Dict, List, Optional, Set, Tuple

# package-relative: config owns _EngineState (mutable shared state)
from . import config as _cfg
from .names import rd

class TVMEmitError(Exception):
    """Typed error for TVM compiler emission violations (16-bit arg range etc.)."""


_TVM_TOKENS: Dict[str, str] = {}


class _TVMOpcodes:
    # Stack & Data
    LOAD_CONST       = 1
    LOAD_GLOBAL      = 2
    STORE_GLOBAL     = 3
    LOAD_FAST        = 4
    STORE_FAST       = 5
    DUP_TOP          = 6
    POP_TOP          = 7
    ROT_TWO          = 8
    ROT_THREE        = 9

    # Exception block management (TVM 4.0): explicit handler-pop so
    # break/continue/return leaving a try frame cannot strand stale handlers.
    POP_EXC_HANDLER  = 250

    # Arithmetic & Bitwise
    BINARY_ADD       = 10
    BINARY_SUB       = 11
    BINARY_MUL       = 12
    BINARY_DIV       = 13
    BINARY_FLOORDIV  = 14
    BINARY_MOD       = 15
    BINARY_POW       = 16
    BINARY_AND       = 17
    BINARY_OR        = 18
    BINARY_XOR       = 19
    BINARY_LSHIFT    = 20
    BINARY_RSHIFT    = 21
    UNARY_NEG        = 22
    UNARY_NOT        = 23
    UNARY_INVERT     = 24
    BINARY_MATMUL    = 25

    # Comparisons
    COMPARE_OP       = 30

    # Control Flow
    JUMP             = 40
    JUMP_IF_TRUE     = 41
    JUMP_IF_FALSE    = 42
    JUMP_IF_FALSE_OR_POP = 43
    JUMP_IF_TRUE_OR_POP  = 44
    RETURN_VALUE     = 45

    # Object / Attribute / Subscript / Deletion
    GET_ATTR         = 50
    SET_ATTR         = 51
    GET_ITEM         = 52
    SET_ITEM         = 53
    DEL_ITEM         = 54
    DEL_ATTR         = 55
    DEL_FAST         = 56
    DEL_GLOBAL       = 57

    # Collections & Unpacking
    BUILD_LIST       = 60
    BUILD_TUPLE      = 61
    BUILD_SET        = 62
    BUILD_DICT       = 63
    UNPACK_SEQUENCE  = 64
    BUILD_SLICE      = 65
    UNPACK_EX        = 66

    # Functions, Calls, Classes & Closures
    MAKE_FUNCTION    = 70
    CALL_FUNCTION    = 71
    CALL_FUNCTION_KW = 72
    BUILD_CLASS      = 73
    IMPORT_NAME      = 74
    IMPORT_FROM      = 75
    CALL_FUNCTION_EX = 76
    LOAD_DEREF       = 77
    STORE_DEREF      = 78

    # Iteration & Exceptions
    GET_ITER         = 80
    FOR_ITER         = 81
    SETUP_FINALLY    = 82
    POP_BLOCK        = 83
    RAISE_VARARGS    = 84
    CHECK_EXC_MATCH  = 85

    # Termination / NOP / Trap
    HALT             = 99
    NOP              = 100
    TRAP             = 101

    # Generators (resumable frames)
    YIELD_VALUE      = 102
    YIELD_FROM       = 103


class _TVMCodeObject:
    """Represents a virtualized code block (Module, Function, Class, or Generator)."""
    def __init__(self, name: str, arg_names: List[str], kwarg_name: Optional[str] = None, vararg_name: Optional[str] = None, kwonly_names: Optional[List[str]] = None, defaults: Optional[Dict[str, Any]] = None):
        self.name = name
        self.arg_names = list(arg_names)
        self.kwonly_names = list(kwonly_names or [])
        self.kwarg_name = kwarg_name
        self.vararg_name = vararg_name
        self.defaults = defaults or {}
        self.instructions: List[Tuple[int, int]] = []
        self.constants: List[Any] = []
        self.names: List[str] = []
        locs = list(arg_names) + list(self.kwonly_names)
        if vararg_name and vararg_name not in locs:
            locs.append(vararg_name)
        if kwarg_name and kwarg_name not in locs:
            locs.append(kwarg_name)
        self.local_names: List[str] = locs
        # Kwonly params that carry defaults (late-bound via body preamble);
        # serialized so the runtime binder can exempt them from the strict
        # missing-argument check (TVM 4.0 GAP-27 refinement).
        self.kwonly_default_names: Tuple[str, ...] = ()

    def get_const_idx(self, val: Any) -> int:
        for idx, c in enumerate(self.constants):
            if type(c) == type(val) and c == val:
                return idx
        self.constants.append(val)
        return len(self.constants) - 1

    def get_name_idx(self, name: str) -> int:
        if name not in self.names:
            self.names.append(name)
        return self.names.index(name)

    def get_local_idx(self, name: str) -> int:
        if name not in self.local_names:
            self.local_names.append(name)
        return self.local_names.index(name)


class _TVMASTCompiler(ast.NodeVisitor):
    """Compiles Python AST statements and expressions into TVM-IR and custom virtual bytecode."""
    def __init__(self, name: str = '<module>', arg_names: List[str] = None, kwonly_names: Optional[List[str]] = None, kwarg_name: Optional[str] = None, vararg_name: Optional[str] = None, defaults: Optional[Dict[str, Any]] = None, is_function: bool = False, is_class: bool = False, vm_level: int = 1, rng: Optional[random.Random] = None):
        self.code_obj = _TVMCodeObject(name, arg_names or [], kwarg_name=kwarg_name, vararg_name=vararg_name, kwonly_names=kwonly_names, defaults=defaults)
        self.is_function = is_function
        self.is_class = is_class
        self.vm_level = vm_level
        self.rng = rng or random.Random()
        self.labels: Dict[int, int] = {}
        self.label_fixups: Dict[int, List[int]] = {}
        self.next_label_id = 0
        self.loop_stack: List[Tuple[int, int]] = []
        # Depth of enclosing SETUP_FINALLY frames (try / with). break/continue
        # crossing these boundaries MUST pop the handler first or the frame's
        # exc_handlers stack retains a stale entry that hijacks a later,
        # unrelated exception (TVM GAP-01/03).
        self.exc_frame_depth = 0
        self.vm_annotations = False
        self._fin_stack: List[List[ast.stmt]] = []
        self.loop_depth = 0
        self.explicit_globals: Set[str] = set()
        self.explicit_nonlocals: Set[str] = set()
        # PERF G2: name indexes emitted as certain-globals (declared via
        # `global x`); the runtime handler skips the O(depth) frame walk for
        # these and reads global_env/builtins directly.
        self.code_obj.global_only_idx: Set[int] = set()

    def new_label(self) -> int:
        lbl = self.next_label_id
        self.next_label_id += 1
        return lbl

    def mark_label(self, label_id: int):
        self.labels[label_id] = len(self.code_obj.instructions)

    def emit(self, op: int, arg: int = 0):
        # FIX (TVM P0): the 3-byte serializer silently truncated args > 0xFFFF,
        # corrupting jump targets / pool indices in large functions.
        if not isinstance(arg, int) or arg < 0 or arg > 0xFFFF:
            raise TVMEmitError(f"opcode {op}: argument out of 16-bit range: {arg!r}")
        self.code_obj.instructions.append((op, arg))

    def emit_jump(self, op: int, target_label_id: int):
        idx = len(self.code_obj.instructions)
        self.code_obj.instructions.append((op, 0))
        if target_label_id not in self.label_fixups:
            self.label_fixups[target_label_id] = []
        self.label_fixups[target_label_id].append(idx)

    def _scan_scope(self, body_nodes: List[ast.stmt]):
        """Pre-scans the lexical scope for global/nonlocal declarations and local assignment targets."""
        for node in body_nodes:
            self._scan_scope_decls(node)
        if self.is_function or self.is_class:
            for node in body_nodes:
                self._scan_scope_stores(node)

    def _scan_scope_decls(self, node: ast.AST):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(node, ast.Global):
            for name in node.names:
                self.explicit_globals.add(name)
        elif isinstance(node, ast.Nonlocal):
            for name in node.names:
                self.explicit_nonlocals.add(name)
        for child in ast.iter_child_nodes(node):
            self._scan_scope_decls(child)

    def _scan_scope_stores(self, node: ast.AST):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name not in self.explicit_globals and node.name not in self.explicit_nonlocals:
                self.code_obj.get_local_idx(node.name)
            return

        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Param)):
            if node.id not in self.explicit_globals and node.id not in self.explicit_nonlocals:
                self.code_obj.get_local_idx(node.id)
        elif isinstance(node, ast.NamedExpr):
            if isinstance(node.target, ast.Name):
                if node.target.id not in self.explicit_globals and node.target.id not in self.explicit_nonlocals:
                    self.code_obj.get_local_idx(node.target.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            if node.name not in self.explicit_globals and node.name not in self.explicit_nonlocals:
                self.code_obj.get_local_idx(node.name)

        for child in ast.iter_child_nodes(node):
            self._scan_scope_stores(child)

    def _store_target(self, target: ast.AST):
        """Helper to lower assignment targets into appropriate STORE opcodes."""
        if isinstance(target, ast.Name):
            if target.id in self.explicit_globals:
                self.emit(_TVMOpcodes.STORE_GLOBAL, self.code_obj.get_name_idx(target.id))
            elif target.id in self.explicit_nonlocals:
                self.emit(_TVMOpcodes.STORE_DEREF, self.code_obj.get_name_idx(target.id))
            elif self.is_class:
                self.emit(_TVMOpcodes.STORE_FAST, self.code_obj.get_local_idx(target.id))
            elif self.is_function and target.id in self.code_obj.local_names:
                self.emit(_TVMOpcodes.STORE_FAST, self.code_obj.get_local_idx(target.id))
            else:
                self.emit(_TVMOpcodes.STORE_GLOBAL, self.code_obj.get_name_idx(target.id))
        elif isinstance(target, ast.Attribute):
            self.visit(target.value)
            idx = self.code_obj.get_name_idx(target.attr)
            self.emit(_TVMOpcodes.SET_ATTR, idx)
        elif isinstance(target, ast.Subscript):
            self.visit(target.value)
            self.visit(target.slice)
            self.emit(_TVMOpcodes.SET_ITEM)
        elif isinstance(target, (ast.Tuple, ast.List)):
            # Check for starred unpacking
            starred_idx = -1
            for idx, elt in enumerate(target.elts):
                if isinstance(elt, ast.Starred):
                    starred_idx = idx
                    break
            if starred_idx >= 0:
                before_cnt = starred_idx
                after_cnt = len(target.elts) - 1 - starred_idx
                self.emit(_TVMOpcodes.UNPACK_EX, before_cnt | (after_cnt << 8))
                for elt in target.elts:
                    if isinstance(elt, ast.Starred):
                        self._store_target(elt.value)
                    else:
                        self._store_target(elt)
            else:
                self.emit(_TVMOpcodes.UNPACK_SEQUENCE, len(target.elts))
                for elt in target.elts:
                    self._store_target(elt)

    # --- Expressions ---

    def visit_Constant(self, node: ast.Constant):
        idx = self.code_obj.get_const_idx(node.value)
        self.emit(_TVMOpcodes.LOAD_CONST, idx)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Store):
            self._store_target(node)
        elif isinstance(node.ctx, ast.Del):
            if node.id in self.explicit_globals:
                self.emit(_TVMOpcodes.DEL_GLOBAL, self.code_obj.get_name_idx(node.id))
            elif node.id in self.explicit_nonlocals:
                self.emit(_TVMOpcodes.DEL_FAST, self.code_obj.get_local_idx(node.id))
            elif (self.is_class or self.is_function) and node.id in self.code_obj.local_names:
                self.emit(_TVMOpcodes.DEL_FAST, self.code_obj.get_local_idx(node.id))
            else:
                self.emit(_TVMOpcodes.DEL_GLOBAL, self.code_obj.get_name_idx(node.id))
        else:
            # Load context
            if node.id in self.explicit_globals:
                _gidx = self.code_obj.get_name_idx(node.id)
                self.emit(_TVMOpcodes.LOAD_GLOBAL, _gidx)
                # PERF G2: declared-global loads skip the runtime frame walk.
                self.code_obj.global_only_idx.add(_gidx)
            elif node.id in self.explicit_nonlocals:
                self.emit(_TVMOpcodes.LOAD_DEREF, self.code_obj.get_name_idx(node.id))
            elif (self.is_class or self.is_function) and node.id in self.code_obj.local_names:
                self.emit(_TVMOpcodes.LOAD_FAST, self.code_obj.get_local_idx(node.id))
            else:
                self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(node.id))

    def visit_BinOp(self, node: ast.BinOp):
        self.visit(node.left)
        self.visit(node.right)
        op_map = {
            ast.Add: _TVMOpcodes.BINARY_ADD,
            ast.Sub: _TVMOpcodes.BINARY_SUB,
            ast.Mult: _TVMOpcodes.BINARY_MUL,
            ast.Div: _TVMOpcodes.BINARY_DIV,
            ast.FloorDiv: _TVMOpcodes.BINARY_FLOORDIV,
            ast.Mod: _TVMOpcodes.BINARY_MOD,
            ast.Pow: _TVMOpcodes.BINARY_POW,
            ast.BitAnd: _TVMOpcodes.BINARY_AND,
            ast.BitOr: _TVMOpcodes.BINARY_OR,
            ast.BitXor: _TVMOpcodes.BINARY_XOR,
            ast.LShift: _TVMOpcodes.BINARY_LSHIFT,
            ast.RShift: _TVMOpcodes.BINARY_RSHIFT,
            ast.MatMult: _TVMOpcodes.BINARY_MATMUL,
        }
        self.emit(op_map.get(type(node.op), _TVMOpcodes.BINARY_ADD))

    def visit_UnaryOp(self, node: ast.UnaryOp):
        self.visit(node.operand)
        if isinstance(node.op, ast.USub):
            self.emit(_TVMOpcodes.UNARY_NEG)
        elif isinstance(node.op, ast.Not):
            self.emit(_TVMOpcodes.UNARY_NOT)
        elif isinstance(node.op, ast.Invert):
            self.emit(_TVMOpcodes.UNARY_INVERT)
        elif isinstance(node.op, ast.UAdd):
            pass

    def visit_TypeAlias(self, node: ast.AST):
        if hasattr(node, 'value'):
            self.visit(node.value)
            if hasattr(node, 'name'):
                self._store_target(node.name)
            else:
                self.emit(_TVMOpcodes.POP_TOP)

    def visit_TryStar(self, node: ast.AST):
        # FIX (GAP-38): except* was silently compiled as a plain try, destroying
        # PEP 654 semantics (ExceptionGroup never split). Fail LOUD instead of
        # silent-wrong-output; stage wrapper logs it and --strict aborts.
        raise TVMEmitError("except* (PEP 654) is not supported by TVM virtualization")

    def visit_BoolOp(self, node: ast.BoolOp):
        # Short-circuiting boolean operations (And / Or)
        is_or = isinstance(node.op, ast.Or)
        lbl_end = self.new_label()
        for idx, val in enumerate(node.values):
            self.visit(val)
            if idx < len(node.values) - 1:
                if is_or:
                    self.emit_jump(_TVMOpcodes.JUMP_IF_TRUE_OR_POP, lbl_end)
                else:
                    self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE_OR_POP, lbl_end)
        self.mark_label(lbl_end)

    def visit_Compare(self, node: ast.Compare):
        cmp_map = {
            ast.Lt: 0, ast.LtE: 1, ast.Eq: 2, ast.NotEq: 3,
            ast.Gt: 4, ast.GtE: 5, ast.In: 6, ast.NotIn: 7,
            ast.Is: 8, ast.IsNot: 9
        }
        if len(node.ops) == 1:
            self.visit(node.left)
            self.visit(node.comparators[0])
            cmp_code = cmp_map.get(type(node.ops[0]), 2)
            self.emit(_TVMOpcodes.COMPARE_OP, cmp_code)
        else:
            # Chained comparison with short-circuiting: a < b < c
            lbl_fail = self.new_label()
            lbl_end = self.new_label()

            self.visit(node.left)
            for idx, (op, comp) in enumerate(zip(node.ops, node.comparators)):
                is_last = (idx == len(node.ops) - 1)
                cmp_code = cmp_map.get(type(op), 2)
                temp_slot = self.code_obj.get_local_idx(f'_$cmp_{self.new_label()}')

                self.visit(comp)
                if not is_last:
                    self.emit(_TVMOpcodes.STORE_FAST, temp_slot)
                    self.emit(_TVMOpcodes.LOAD_FAST, temp_slot)

                self.emit(_TVMOpcodes.COMPARE_OP, cmp_code)
                if not is_last:
                    self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
                    self.emit(_TVMOpcodes.LOAD_FAST, temp_slot)
                else:
                    self.emit_jump(_TVMOpcodes.JUMP, lbl_end)

            self.mark_label(lbl_fail)
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(False))
            self.mark_label(lbl_end)

    def visit_JoinedStr(self, node: ast.JoinedStr):
        for val in node.values:
            self.visit(val)
        self.emit(_TVMOpcodes.BUILD_LIST, len(node.values))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(''))
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('join'))
        self.emit(_TVMOpcodes.ROT_TWO)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

    def visit_FormattedValue(self, node: ast.FormattedValue):
        self.visit(node.value)
        # Handle conversion (!s=115, !r=114, !a=97)
        if node.conversion == 115:
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('str'))
            self.emit(_TVMOpcodes.ROT_TWO)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        elif node.conversion == 114:
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('repr'))
            self.emit(_TVMOpcodes.ROT_TWO)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        elif node.conversion == 97:
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('ascii'))
            self.emit(_TVMOpcodes.ROT_TWO)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

        # Handle format_spec
        if node.format_spec:
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('format'))
            self.emit(_TVMOpcodes.ROT_TWO)
            self.visit(node.format_spec)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 2)
        elif node.conversion == -1:
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('str'))
            self.emit(_TVMOpcodes.ROT_TWO)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

    def visit_NamedExpr(self, node: ast.NamedExpr):
        # Assignment expression (walrus operator :=)
        self.visit(node.value)
        self.emit(_TVMOpcodes.DUP_TOP)
        self._store_target(node.target)

    def visit_IfExp(self, node: ast.IfExp):
        # Ternary conditional expression: a if cond else b
        lbl_else = self.new_label()
        lbl_end = self.new_label()
        self.visit(node.test)
        self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_else)
        self.visit(node.body)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_end)
        self.mark_label(lbl_else)
        self.visit(node.orelse)
        self.mark_label(lbl_end)

    def visit_Await(self, node: ast.Await):
        tmp_slot = self.code_obj.get_local_idx(f'_$await_tmp_{self.new_label()}')
        self.visit(node.value)
        self.emit(_TVMOpcodes.STORE_FAST, tmp_slot)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['await_fn']))
        self.emit(_TVMOpcodes.LOAD_FAST, tmp_slot)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

    def visit_Call(self, node: ast.Call):
        has_starred = any(isinstance(a, ast.Starred) for a in node.args)
        has_starred_kw = any(kw.arg is None for kw in node.keywords)
        if has_starred or has_starred_kw:
            self.emit(_TVMOpcodes.BUILD_LIST, 0)
            lst_idx = self.code_obj.get_local_idx(f'_$call_args_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, lst_idx)
            for a in node.args:
                if isinstance(a, ast.Starred):
                    self.emit(_TVMOpcodes.LOAD_FAST, lst_idx)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('extend'))
                    self.visit(a.value)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
                else:
                    self.emit(_TVMOpcodes.LOAD_FAST, lst_idx)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('append'))
                    self.visit(a)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)

            self.emit(_TVMOpcodes.BUILD_DICT, 0)
            kw_idx = self.code_obj.get_local_idx(f'_$call_kw_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, kw_idx)
            for kw in node.keywords:
                if kw.arg is None:
                    self.emit(_TVMOpcodes.LOAD_FAST, kw_idx)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('update'))
                    self.visit(kw.value)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
                else:
                    self.visit(kw.value)
                    self.emit(_TVMOpcodes.LOAD_FAST, kw_idx)
                    self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(kw.arg))
                    self.emit(_TVMOpcodes.SET_ITEM)

            self.visit(node.func)
            self.emit(_TVMOpcodes.LOAD_FAST, lst_idx)
            self.emit(_TVMOpcodes.LOAD_FAST, kw_idx)
            self.emit(_TVMOpcodes.CALL_FUNCTION_EX, 1)
        else:
            self.visit(node.func)
            for arg in node.args:
                self.visit(arg)
            if node.keywords:
                for kw in node.keywords:
                    k_idx = self.code_obj.get_const_idx(kw.arg)
                    self.emit(_TVMOpcodes.LOAD_CONST, k_idx)
                    self.visit(kw.value)
                self.emit(_TVMOpcodes.CALL_FUNCTION_KW, len(node.args) | (len(node.keywords) << 8))
            else:
                self.emit(_TVMOpcodes.CALL_FUNCTION, len(node.args))

    def visit_Attribute(self, node: ast.Attribute):
        self.visit(node.value)
        idx = self.code_obj.get_name_idx(node.attr)
        if isinstance(node.ctx, ast.Load):
            self.emit(_TVMOpcodes.GET_ATTR, idx)
        elif isinstance(node.ctx, ast.Store):
            self.emit(_TVMOpcodes.SET_ATTR, idx)
        elif isinstance(node.ctx, ast.Del):
            self.emit(_TVMOpcodes.DEL_ATTR, idx)

    def visit_Subscript(self, node: ast.Subscript):
        self.visit(node.value)
        self.visit(node.slice)
        if isinstance(node.ctx, ast.Load):
            self.emit(_TVMOpcodes.GET_ITEM)
        elif isinstance(node.ctx, ast.Store):
            self.emit(_TVMOpcodes.SET_ITEM)
        elif isinstance(node.ctx, ast.Del):
            self.emit(_TVMOpcodes.DEL_ITEM)

    def visit_List(self, node: ast.List):
        has_starred = any(isinstance(e, ast.Starred) for e in node.elts)
        if has_starred:
            self.emit(_TVMOpcodes.BUILD_LIST, 0)
            lst_slot = self.code_obj.get_local_idx(f'_$list_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, lst_slot)
            for e in node.elts:
                if isinstance(e, ast.Starred):
                    self.emit(_TVMOpcodes.LOAD_FAST, lst_slot)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('extend'))
                    self.visit(e.value)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
                else:
                    self.emit(_TVMOpcodes.LOAD_FAST, lst_slot)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('append'))
                    self.visit(e)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
            self.emit(_TVMOpcodes.LOAD_FAST, lst_slot)
        else:
            for elt in node.elts:
                self.visit(elt)
            self.emit(_TVMOpcodes.BUILD_LIST, len(node.elts))

    def visit_Tuple(self, node: ast.Tuple):
        has_starred = any(isinstance(e, ast.Starred) for e in node.elts)
        if has_starred:
            self.emit(_TVMOpcodes.BUILD_LIST, 0)
            lst_slot = self.code_obj.get_local_idx(f'_$tup_lst_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, lst_slot)
            for e in node.elts:
                if isinstance(e, ast.Starred):
                    self.emit(_TVMOpcodes.LOAD_FAST, lst_slot)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('extend'))
                    self.visit(e.value)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
                else:
                    self.emit(_TVMOpcodes.LOAD_FAST, lst_slot)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('append'))
                    self.visit(e)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('tuple'))
            self.emit(_TVMOpcodes.LOAD_FAST, lst_slot)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        else:
            for elt in node.elts:
                self.visit(elt)
            self.emit(_TVMOpcodes.BUILD_TUPLE, len(node.elts))

    def visit_Set(self, node: ast.Set):
        has_starred = any(isinstance(e, ast.Starred) for e in node.elts)
        if has_starred:
            self.emit(_TVMOpcodes.BUILD_SET, 0)
            set_slot = self.code_obj.get_local_idx(f'_$set_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, set_slot)
            for e in node.elts:
                if isinstance(e, ast.Starred):
                    self.emit(_TVMOpcodes.LOAD_FAST, set_slot)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('update'))
                    self.visit(e.value)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
                else:
                    self.emit(_TVMOpcodes.LOAD_FAST, set_slot)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('add'))
                    self.visit(e)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
            self.emit(_TVMOpcodes.LOAD_FAST, set_slot)
        else:
            for elt in node.elts:
                self.visit(elt)
            self.emit(_TVMOpcodes.BUILD_SET, len(node.elts))

    def visit_Dict(self, node: ast.Dict):
        has_unpacking = any(k is None for k in node.keys)
        if has_unpacking:
            self.emit(_TVMOpcodes.BUILD_DICT, 0)
            dict_slot = self.code_obj.get_local_idx(f'_$dict_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, dict_slot)
            for k, v in zip(node.keys, node.values):
                if k is None:
                    self.emit(_TVMOpcodes.LOAD_FAST, dict_slot)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('update'))
                    self.visit(v)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
                else:
                    self.visit(v)
                    self.emit(_TVMOpcodes.LOAD_FAST, dict_slot)
                    self.visit(k)
                    self.emit(_TVMOpcodes.SET_ITEM)
            self.emit(_TVMOpcodes.LOAD_FAST, dict_slot)
        else:
            for k, v in zip(node.keys, node.values):
                self.visit(k)
                self.visit(v)
            self.emit(_TVMOpcodes.BUILD_DICT, len(node.keys))

    def visit_Slice(self, node: ast.Slice):
        if node.lower: self.visit(node.lower)
        else: self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        if node.upper: self.visit(node.upper)
        else: self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        if node.step: self.visit(node.step)
        else: self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.BUILD_SLICE, 3)

    # --- Statements & Control Flow Lowering ---

    def visit_Expr(self, node: ast.Expr):
        self.visit(node.value)
        if not (getattr(self, 'is_generator', False) and isinstance(node.value, (ast.Yield, ast.YieldFrom))):
            self.emit(_TVMOpcodes.POP_TOP)

    def visit_Assign(self, node: ast.Assign):
        self.visit(node.value)
        if len(node.targets) > 1:
            for target in node.targets[:-1]:
                self.emit(_TVMOpcodes.DUP_TOP)
                self._store_target(target)
            self._store_target(node.targets[-1])
        else:
            self._store_target(node.targets[0])

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if node.value:
            self.visit(node.value)
            self._store_target(node.target)
        elif isinstance(node.target, ast.Name):
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
            self._store_target(node.target)

        # Annotation storage (--vm-annotations y): emit __annotations__[name] = type
        if self.vm_annotations and node.annotation:
            self.visit(node.annotation)
            self.emit(_TVMOpcodes.LOAD_GLOBAL,
                      self.code_obj.get_name_idx('__annotations__'))
            tgt_name = getattr(node.target, 'id',
                               getattr(node.target, 'attr', ''))
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(tgt_name))
            self.emit(_TVMOpcodes.STORE_SUBSCR)

    def visit_AugAssign(self, node: ast.AugAssign):
        op_map = {
            ast.Add: _TVMOpcodes.BINARY_ADD,
            ast.Sub: _TVMOpcodes.BINARY_SUB,
            ast.Mult: _TVMOpcodes.BINARY_MUL,
            ast.Div: _TVMOpcodes.BINARY_DIV,
            ast.FloorDiv: _TVMOpcodes.BINARY_FLOORDIV,
            ast.Mod: _TVMOpcodes.BINARY_MOD,
            ast.Pow: _TVMOpcodes.BINARY_POW,
            ast.BitAnd: _TVMOpcodes.BINARY_AND,
            ast.BitOr: _TVMOpcodes.BINARY_OR,
            ast.BitXor: _TVMOpcodes.BINARY_XOR,
            ast.LShift: _TVMOpcodes.BINARY_LSHIFT,
            ast.RShift: _TVMOpcodes.BINARY_RSHIFT,
            ast.MatMult: _TVMOpcodes.BINARY_MATMUL,
        }
        bin_op = op_map.get(type(node.op), _TVMOpcodes.BINARY_ADD)

        if isinstance(node.target, ast.Name):
            self.visit(ast.Name(id=node.target.id, ctx=ast.Load()))
            self.visit(node.value)
            self.emit(bin_op)
            self._store_target(node.target)
        elif isinstance(node.target, ast.Attribute):
            # Evaluate target object ONCE and store in temp slot
            self.visit(node.target.value)
            obj_slot = self.code_obj.get_local_idx(f'_$aug_obj_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, obj_slot)

            self.emit(_TVMOpcodes.LOAD_FAST, obj_slot)
            attr_idx = self.code_obj.get_name_idx(node.target.attr)
            self.emit(_TVMOpcodes.GET_ATTR, attr_idx)

            self.visit(node.value)
            self.emit(bin_op)

            # SET_ATTR expects stack: [new_val, obj]
            self.emit(_TVMOpcodes.LOAD_FAST, obj_slot)
            self.emit(_TVMOpcodes.SET_ATTR, attr_idx)
        elif isinstance(node.target, ast.Subscript):
            # Evaluate container and slice ONCE
            self.visit(node.target.value)
            cnt_slot = self.code_obj.get_local_idx(f'_$aug_cnt_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, cnt_slot)

            self.visit(node.target.slice)
            idx_slot = self.code_obj.get_local_idx(f'_$aug_idx_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, idx_slot)

            self.emit(_TVMOpcodes.LOAD_FAST, cnt_slot)
            self.emit(_TVMOpcodes.LOAD_FAST, idx_slot)
            self.emit(_TVMOpcodes.GET_ITEM)

            self.visit(node.value)
            self.emit(bin_op)

            # SET_ITEM expects stack: [new_val, container, slice]
            self.emit(_TVMOpcodes.LOAD_FAST, cnt_slot)
            self.emit(_TVMOpcodes.LOAD_FAST, idx_slot)
            self.emit(_TVMOpcodes.SET_ITEM)

    def visit_Delete(self, node: ast.Delete):
        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.id in self.explicit_globals:
                    self.emit(_TVMOpcodes.DEL_GLOBAL, self.code_obj.get_name_idx(target.id))
                elif target.id in self.explicit_nonlocals:
                    self.emit(_TVMOpcodes.DEL_FAST, self.code_obj.get_local_idx(target.id))
                elif self.is_class or (self.is_function and target.id in self.code_obj.local_names):
                    self.emit(_TVMOpcodes.DEL_FAST, self.code_obj.get_local_idx(target.id))
                else:
                    self.emit(_TVMOpcodes.DEL_GLOBAL, self.code_obj.get_name_idx(target.id))
            elif isinstance(target, ast.Subscript):
                self.visit(target.value)
                self.visit(target.slice)
                self.emit(_TVMOpcodes.DEL_ITEM)
            elif isinstance(target, ast.Attribute):
                self.visit(target.value)
                self.emit(_TVMOpcodes.DEL_ATTR, self.code_obj.get_name_idx(target.attr))

    def visit_Assert(self, node: ast.Assert):
        lbl_ok = self.new_label()
        self.visit(node.test)
        self.emit_jump(_TVMOpcodes.JUMP_IF_TRUE, lbl_ok)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('AssertionError'))
        if node.msg:
            self.visit(node.msg)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        else:
            self.emit(_TVMOpcodes.CALL_FUNCTION, 0)
        self.emit(_TVMOpcodes.RAISE_VARARGS)
        self.mark_label(lbl_ok)

    def visit_Global(self, node: ast.Global):
        for name in node.names:
            self.explicit_globals.add(name)

    def visit_Nonlocal(self, node: ast.Nonlocal):
        for name in node.names:
            self.explicit_nonlocals.add(name)

    def visit_Pass(self, node: ast.Pass):
        self.emit(_TVMOpcodes.NOP)

    def visit_Raise(self, node: ast.Raise):
        if node.cause:
            # handler pops cause first, then exc -> push exc first
            self.visit(node.exc)
            self.visit(node.cause)
            self.emit(_TVMOpcodes.RAISE_VARARGS, 2)
        elif node.exc:
            self.visit(node.exc)
            self.emit(_TVMOpcodes.RAISE_VARARGS)
        else:
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
            self.emit(_TVMOpcodes.RAISE_VARARGS)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        is_gen = self._contains_yield_in_scope(node.body)
        # FIX (TVM GAP-25): positional-only params were silently dropped from the
        # signature, misrouting positional binding and voiding the '/' constraint.
        arg_names = [a.arg for a in getattr(node.args, 'posonlyargs', [])] + [a.arg for a in node.args.args]
        kwonly_names = [a.arg for a in node.args.kwonlyargs] if hasattr(node.args, 'kwonlyargs') else []
        vararg_name = node.args.vararg.arg if node.args.vararg else None
        kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
        sub_compiler = _TVMASTCompiler(name=node.name, arg_names=arg_names, kwonly_names=kwonly_names, kwarg_name=kwarg_name, vararg_name=vararg_name, is_function=True, vm_level=self.vm_level, rng=self.rng)
        sub_compiler._scan_scope(node.body)
        # Kwonly params WITH defaults: sentinel replaced by body preamble at
        # call time; the runtime binder must not treat them as missing.
        sub_compiler.code_obj.kwonly_default_names = tuple(
            a.arg for a, d in zip(getattr(node.args, 'kwonlyargs', []), getattr(node.args, 'kw_defaults', []))
            if d is not None
        )

        # Handle default arguments
        # Positional defaults are evaluated ONCE at function-creation time
        # (native CPython semantics) via the __vm_bind_defaults__ registry.
        if node.args.defaults:
            dfl_slot = self.code_obj.get_local_idx(f'_$dflt_{self.new_label()}')
            pos_names = [a.arg for a in node.args.args[-len(node.args.defaults):]]
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(tuple(pos_names)))
            for d_expr in node.args.defaults:
                self.visit(d_expr)
            self.emit(_TVMOpcodes.BUILD_TUPLE, len(node.args.defaults))
            self.emit(_TVMOpcodes.BUILD_TUPLE, 2)
            self.emit(_TVMOpcodes.STORE_FAST, dfl_slot)

        if hasattr(node.args, 'kw_defaults') and node.args.kw_defaults:
            for arg_node, def_node in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if def_node is not None:
                    arg_idx = sub_compiler.code_obj.get_local_idx(arg_node.arg)
                    sub_compiler.emit(_TVMOpcodes.LOAD_FAST, arg_idx)
                    sub_compiler.emit(_TVMOpcodes.LOAD_GLOBAL, sub_compiler.code_obj.get_name_idx(_TVM_TOKENS['no_arg']))
                    sub_compiler.emit(_TVMOpcodes.COMPARE_OP, 8)
                    lbl_has_val = sub_compiler.new_label()
                    sub_compiler.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_has_val)
                    sub_compiler.visit(def_node)
                    sub_compiler.emit(_TVMOpcodes.STORE_FAST, arg_idx)
                    sub_compiler.mark_label(lbl_has_val)

        if is_gen:
            sub_compiler.is_generator = True
            for stmt in node.body:
                sub_compiler.visit(stmt)
        else:
            for stmt in node.body:
                sub_compiler.visit(stmt)
        sub_code = sub_compiler.finalize()

        idx = self.code_obj.get_const_idx(sub_code)
        if node.args.defaults:
            self.emit(_TVMOpcodes.LOAD_FAST, dfl_slot)
        self.emit(_TVMOpcodes.LOAD_CONST, idx)
        self.emit(_TVMOpcodes.MAKE_FUNCTION, (2 if is_gen else 0) | (8 if node.args.defaults else 0))  # bit1(2)=gen bit3(8)=defaults

        # Apply decorators if present
        for dec in reversed(node.decorator_list):
            self.visit(dec)
            self.emit(_TVMOpcodes.ROT_TWO)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

        self._store_target(ast.Name(id=node.name, ctx=ast.Store()))

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # FIX (TVM P0): this visitor previously never finalized the sub compiler
        # nor stored the code object into constants -> UnboundLocalError on `idx`
        # for EVERY async def compiled under --vm-obf. Mirrors visit_FunctionDef.
        arg_names = [a.arg for a in getattr(node.args, 'posonlyargs', [])] + [a.arg for a in node.args.args]
        kwonly_names = [a.arg for a in node.args.kwonlyargs] if hasattr(node.args, 'kwonlyargs') else []
        vararg_name = node.args.vararg.arg if node.args.vararg else None
        kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
        sub_compiler = _TVMASTCompiler(name=node.name, arg_names=arg_names, kwonly_names=kwonly_names, kwarg_name=kwarg_name, vararg_name=vararg_name, is_function=True, vm_level=self.vm_level, rng=self.rng)
        sub_compiler._scan_scope(node.body)
        sub_compiler.is_async = True
        # Detect async-generator BEFORE compiling so visit_Yield emits suspends.
        is_agen_pre = self._contains_yield_in_scope(node.body)
        if is_agen_pre:
            sub_compiler.is_generator = True

        if node.args.defaults:
            dfl_slot = self.code_obj.get_local_idx(f'_$dflt_{self.new_label()}')
            pos_names = [a.arg for a in node.args.args[-len(node.args.defaults):]]
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(tuple(pos_names)))
            for d_expr in node.args.defaults:
                self.visit(d_expr)
            self.emit(_TVMOpcodes.BUILD_TUPLE, len(node.args.defaults))
            self.emit(_TVMOpcodes.BUILD_TUPLE, 2)
            self.emit(_TVMOpcodes.STORE_FAST, dfl_slot)

        if hasattr(node.args, 'kw_defaults') and node.args.kw_defaults:
            for arg_node, def_node in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if def_node is not None:
                    arg_idx = sub_compiler.code_obj.get_local_idx(arg_node.arg)
                    sub_compiler.emit(_TVMOpcodes.LOAD_FAST, arg_idx)
                    sub_compiler.emit(_TVMOpcodes.LOAD_GLOBAL, sub_compiler.code_obj.get_name_idx(_TVM_TOKENS['no_arg']))
                    sub_compiler.emit(_TVMOpcodes.COMPARE_OP, 8)
                    lbl_has_val_a = sub_compiler.new_label()
                    sub_compiler.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_has_val_a)
                    sub_compiler.visit(def_node)
                    sub_compiler.emit(_TVMOpcodes.STORE_FAST, arg_idx)
                    sub_compiler.mark_label(lbl_has_val_a)

        # Record which kwonly params carry defaults: their sentinel is replaced
        # by the body preamble (late-bound channel), so the binder's strict
        # missing-arg check must skip them (TVM 4.0 GAP-27 refinement).
        # FIX (perf-wave verification): this previously referenced an undefined
        # `_fn_code`, NameError-crashing EVERY async def with kwonly defaults
        # under --vm-obf; mirrors visit_FunctionDef below.
        sub_compiler.code_obj.kwonly_default_names = tuple(
            a.arg for a, d in zip(getattr(node.args, 'kwonlyargs', []), getattr(node.args, 'kw_defaults', []))
            if d is not None
        )
        for stmt in node.body:
            sub_compiler.visit(stmt)
        sub_code = sub_compiler.finalize()

        idx = self.code_obj.get_const_idx(sub_code)
        mk_flags = (1 | 2) if is_agen_pre else 1
        if node.args.defaults:
            self.emit(_TVMOpcodes.LOAD_FAST, dfl_slot)
        self.emit(_TVMOpcodes.LOAD_CONST, idx)
        self.emit(_TVMOpcodes.MAKE_FUNCTION, mk_flags | (8 if node.args.defaults else 0))

        for dec in reversed(node.decorator_list):
            self.visit(dec)
            self.emit(_TVMOpcodes.ROT_TWO)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

        self._store_target(ast.Name(id=node.name, ctx=ast.Store()))

    def visit_Lambda(self, node: ast.Lambda):
        # FIX (TVM GAP-25): positional-only params included.
        arg_names = [a.arg for a in getattr(node.args, 'posonlyargs', [])] + [a.arg for a in node.args.args]
        kwonly_names = [a.arg for a in node.args.kwonlyargs] if hasattr(node.args, 'kwonlyargs') else []
        vararg_name = node.args.vararg.arg if node.args.vararg else None
        kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
        sub_compiler = _TVMASTCompiler(name='<lambda>', arg_names=arg_names, kwonly_names=kwonly_names, kwarg_name=kwarg_name, vararg_name=vararg_name, is_function=True, vm_level=self.vm_level, rng=self.rng)

        if node.args.defaults:
            num_defaults = len(node.args.defaults)
            default_args = node.args.args[-num_defaults:]
            for arg_node, def_node in zip(default_args, node.args.defaults):
                arg_idx = sub_compiler.code_obj.get_local_idx(arg_node.arg)
                sub_compiler.emit(_TVMOpcodes.LOAD_FAST, arg_idx)
                sub_compiler.emit(_TVMOpcodes.LOAD_GLOBAL, sub_compiler.code_obj.get_name_idx(_TVM_TOKENS['no_arg']))
                sub_compiler.emit(_TVMOpcodes.COMPARE_OP, 8)
                lbl_has = sub_compiler.new_label()
                sub_compiler.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_has)
                sub_compiler.visit(def_node)
                sub_compiler.emit(_TVMOpcodes.STORE_FAST, arg_idx)
                sub_compiler.mark_label(lbl_has)

        if hasattr(node.args, 'kw_defaults') and node.args.kw_defaults:
            for arg_node, def_node in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if def_node is not None:
                    arg_idx = sub_compiler.code_obj.get_local_idx(arg_node.arg)
                    sub_compiler.emit(_TVMOpcodes.LOAD_FAST, arg_idx)
                    sub_compiler.emit(_TVMOpcodes.LOAD_GLOBAL, sub_compiler.code_obj.get_name_idx(_TVM_TOKENS['no_arg']))
                    sub_compiler.emit(_TVMOpcodes.COMPARE_OP, 8)
                    lbl_has = sub_compiler.new_label()
                    sub_compiler.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_has)
                    sub_compiler.visit(def_node)
                    sub_compiler.emit(_TVMOpcodes.STORE_FAST, arg_idx)
                    sub_compiler.mark_label(lbl_has)

        sub_compiler.visit(ast.Return(value=node.body))
        sub_code = sub_compiler.finalize()
        idx = self.code_obj.get_const_idx(sub_code)
        self.emit(_TVMOpcodes.LOAD_CONST, idx)
        self.emit(_TVMOpcodes.MAKE_FUNCTION, 0)

    def _emit_comprehension(self, node, build_opname, acc_name, emit_element):
        """Shared multi-generator comprehension emitter (list/set/dict/genexpr).
        Correctly nests every generator clause instead of only generators[0]."""
        target_names = ['.0']
        for g in node.generators:
            for n in ast.walk(g.target):
                if isinstance(n, ast.Name) and n.id not in target_names:
                    target_names.append(n.id)

        sub_compiler = _TVMASTCompiler(name=f'<{acc_name[2:]}comp>', arg_names=target_names,
                                       is_function=True, vm_level=self.vm_level, rng=self.rng)
        sub_compiler.emit(getattr(_TVMOpcodes, build_opname), 0)
        acc_idx = sub_compiler.code_obj.get_local_idx(acc_name)
        sub_compiler.emit(_TVMOpcodes.STORE_FAST, acc_idx)

        heads = []
        exits = []
        for gi, gen in enumerate(node.generators):
            head = sub_compiler.new_label()
            exit_l = sub_compiler.new_label()
            heads.append(head)
            exits.append(exit_l)
            if gi == 0:
                sub_compiler.mark_label(head)
                sub_compiler.emit(_TVMOpcodes.LOAD_FAST, sub_compiler.code_obj.get_local_idx('.0'))
            else:
                slot_idx = sub_compiler.code_obj.get_local_idx(f'_$g{gi}')
                sub_compiler.visit(gen.iter)
                sub_compiler.emit(_TVMOpcodes.GET_ITER)
                sub_compiler.emit(_TVMOpcodes.STORE_FAST, slot_idx)
                sub_compiler.mark_label(head)
                sub_compiler.emit(_TVMOpcodes.LOAD_FAST, slot_idx)
            sub_compiler.emit_jump(_TVMOpcodes.FOR_ITER, exit_l)
            sub_compiler._store_target(gen.target)
            for if_expr in gen.ifs:
                sub_compiler.visit(if_expr)
                sub_compiler.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, head)

        emit_element(sub_compiler, acc_idx)

        for gi in range(len(node.generators) - 1, -1, -1):
            sub_compiler.emit_jump(_TVMOpcodes.JUMP, heads[gi])
            sub_compiler.mark_label(exits[gi])

        sub_compiler.emit(_TVMOpcodes.LOAD_FAST, acc_idx)
        return sub_compiler

    def _emit_async_comprehension(self, node, kind):
        """Desugar `[x async for ...]`, `{...}`, dict/set/gen variants into an
        inline async helper function that the caller awaits. Returns after the
        resolved iterable has been pushed onto the stack."""
        lbl = self.new_label()
        fn_name = f'_$acomp_fn_{lbl}'
        acc_name = f'_$acomp_{lbl}'

        if kind == 'dict':
            acc_expr = ast.Dict(keys=[], values=[])
            append_call = ast.Call(
                func=ast.Attribute(value=ast.Name(id=acc_name, ctx=ast.Load()), attr='setitem', ctx=ast.Load()),
                args=[], keywords=[])
            # dict.append doesn't exist; build via setitem assignment instead
            body_appends = None
        else:
            method = {'list': 'append', 'set': 'add', 'gen': 'append'}[kind]
            acc_expr = ast.List(elts=[]) if kind in ('list', 'gen') else ast.Set(elts=[])

        # Build innermost append/emit statement(s)
        def make_emit():
            if kind == 'dict':
                return ast.Assign(
                    targets=[ast.Subscript(value=ast.Name(id=acc_name, ctx=ast.Load()),
                                           slice=self._clone_ctx(node.key), ctx=ast.Store())],
                    value=node.value)
            return ast.Expr(value=ast.Call(
                func=ast.Attribute(value=ast.Name(id=acc_name, ctx=ast.Load()), attr=method, ctx=ast.Load()),
                args=[node.elt], keywords=[]))

        # Nest generators (first may be async; the rest are sync per grammar)
        g0 = node.generators[0]
        innermost = [make_emit()]
        for if_expr in reversed(g0.ifs):
            innermost = [ast.If(test=if_expr, body=innermost, orelse=[])]
        loop = ast.AsyncFor(target=g0.target, iter=g0.iter, body=innermost, orelse=[])
        current = [loop]
        for g in node.generators[1:]:
            inner2 = current
            for if_expr in reversed(g.ifs):
                inner2 = [ast.If(test=if_expr, body=inner2, orelse=[])]
            current = [ast.For(target=g.target, iter=g.iter, body=inner2, orelse=[])]

        fn_def = ast.AsyncFunctionDef(
            name=fn_name,
            args=ast.arguments(posonlyargs=[], args=[], vararg=None, kwonlyargs=[],
                               kw_defaults=[], kwarg=None, defaults=[]),
            body=[ast.Assign(targets=[ast.Name(id=acc_name, ctx=ast.Store())], value=acc_expr)] + current +
                 [ast.Return(value=ast.Name(id=acc_name, ctx=ast.Load()))],
            decorator_list=[], returns=None, type_comment=None)

        # Compile the helper as an immediate async closure: MAKE_FUNCTION leaves
        # it on the stack; call it and await the returned coroutine.
        sub_compiler = _TVMASTCompiler(
            name=fn_name,
            arg_names=[], kwonly_names=[], kwarg_name=None, vararg_name=None,
            is_function=True, vm_level=self.vm_level, rng=self.rng)
        sub_compiler._scan_scope(fn_def.body)
        sub_compiler.is_async = True
        for stmt in fn_def.body:
            sub_compiler.visit(stmt)
        sub_code = sub_compiler.finalize()

        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(sub_code))
        self.emit(_TVMOpcodes.MAKE_FUNCTION, 1)          # async
        self.emit(_TVMOpcodes.CALL_FUNCTION, 0)          # -> coroutine
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['await_fn']))
        self.emit(_TVMOpcodes.ROT_TWO)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)          # -> resolved iterable

    @staticmethod
    def _clone_ctx(n):
        import copy as _c
        return _c.deepcopy(n)

    def visit_ListComp(self, node: ast.ListComp):
        if getattr(node.generators[0], 'is_async', False):
            return self._emit_async_comprehension(node, 'list')

        def emit_element(sc, acc_idx):
            sc.emit(_TVMOpcodes.LOAD_FAST, acc_idx)
            sc.emit(_TVMOpcodes.GET_ATTR, sc.code_obj.get_name_idx('append'))
            sc.visit(node.elt)
            sc.emit(_TVMOpcodes.CALL_FUNCTION, 1)
            sc.emit(_TVMOpcodes.POP_TOP)

        sub_compiler = self._emit_comprehension(node, 'BUILD_LIST', '_$lst', emit_element)
        sub_compiler.emit(_TVMOpcodes.RETURN_VALUE)
        sub_code = sub_compiler.finalize()
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(sub_code))
        self.emit(_TVMOpcodes.MAKE_FUNCTION, 0)
        self.visit(node.generators[0].iter)
        self.emit(_TVMOpcodes.GET_ITER)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

    def visit_SetComp(self, node: ast.SetComp):
        if getattr(node.generators[0], 'is_async', False):
            return self._emit_async_comprehension(node, 'set')

        def emit_element(sc, acc_idx):
            sc.emit(_TVMOpcodes.LOAD_FAST, acc_idx)
            sc.emit(_TVMOpcodes.GET_ATTR, sc.code_obj.get_name_idx('add'))
            sc.visit(node.elt)
            sc.emit(_TVMOpcodes.CALL_FUNCTION, 1)
            sc.emit(_TVMOpcodes.POP_TOP)

        sub_compiler = self._emit_comprehension(node, 'BUILD_SET', '_$set', emit_element)
        sub_compiler.emit(_TVMOpcodes.RETURN_VALUE)
        sub_code = sub_compiler.finalize()
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(sub_code))
        self.emit(_TVMOpcodes.MAKE_FUNCTION, 0)
        self.visit(node.generators[0].iter)
        self.emit(_TVMOpcodes.GET_ITER)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

    def visit_DictComp(self, node: ast.DictComp):
        if getattr(node.generators[0], 'is_async', False):
            return self._emit_async_comprehension(node, 'dict')

        def emit_element(sc, acc_idx):
            sc.visit(node.value)
            sc.emit(_TVMOpcodes.LOAD_FAST, acc_idx)
            sc.visit(node.key)
            sc.emit(_TVMOpcodes.SET_ITEM)

        sub_compiler = self._emit_comprehension(node, 'BUILD_DICT', '_$dict', emit_element)
        sub_compiler.emit(_TVMOpcodes.RETURN_VALUE)
        sub_code = sub_compiler.finalize()
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(sub_code))
        self.emit(_TVMOpcodes.MAKE_FUNCTION, 0)
        self.visit(node.generators[0].iter)
        self.emit(_TVMOpcodes.GET_ITER)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

    def visit_GeneratorExp(self, node: ast.GeneratorExp):
        if getattr(node.generators[0], 'is_async', False):
            return self._emit_async_comprehension(node, 'gen')

        def emit_element(sc, acc_idx):
            sc.emit(_TVMOpcodes.LOAD_FAST, acc_idx)
            sc.emit(_TVMOpcodes.GET_ATTR, sc.code_obj.get_name_idx('append'))
            sc.visit(node.elt)
            sc.emit(_TVMOpcodes.CALL_FUNCTION, 1)
            sc.emit(_TVMOpcodes.POP_TOP)

        sub_compiler = self._emit_comprehension(node, 'BUILD_LIST', '_$lst', emit_element)
        sub_compiler.emit(_TVMOpcodes.GET_ITER)
        sub_compiler.emit(_TVMOpcodes.RETURN_VALUE)
        sub_code = sub_compiler.finalize()
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(sub_code))
        self.emit(_TVMOpcodes.MAKE_FUNCTION, 0)
        self.visit(node.generators[0].iter)
        self.emit(_TVMOpcodes.GET_ITER)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

    def visit_ClassDef(self, node: ast.ClassDef):
        sub_compiler = _TVMASTCompiler(name=node.name, arg_names=[], is_function=True, is_class=True, vm_level=self.vm_level, rng=self.rng)
        sub_compiler._scan_scope(node.body)
        for stmt in node.body:
            sub_compiler.visit(stmt)
        sub_code = sub_compiler.finalize()

        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(node.name))
        for b in node.bases:
            self.visit(b)
        self.emit(_TVMOpcodes.BUILD_TUPLE, len(node.bases))

        has_meta = False
        for kw in node.keywords:
            if kw.arg == 'metaclass':
                self.visit(kw.value)
                has_meta = True
                break
        if not has_meta:
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))

        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(sub_code))
        self.emit(_TVMOpcodes.BUILD_CLASS, 0)

        for dec in reversed(node.decorator_list):
            self.visit(dec)
            self.emit(_TVMOpcodes.ROT_TWO)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

        self._store_target(ast.Name(id=node.name, ctx=ast.Store()))

    def visit_If(self, node: ast.If):
        lbl_else = self.new_label()
        lbl_end = self.new_label()

        self.visit(node.test)
        self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_else)
        for stmt in node.body:
            self.visit(stmt)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_end)

        self.mark_label(lbl_else)
        if node.orelse:
            for stmt in node.orelse:
                self.visit(stmt)
        self.mark_label(lbl_end)

    def visit_While(self, node: ast.While):
        lbl_head = self.new_label()
        lbl_break = self.new_label()
        lbl_exit = self.new_label()
        lbl_end = self.new_label()

        self.mark_label(lbl_head)
        self.visit(node.test)
        self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_exit)

        self.loop_stack.append((lbl_head, lbl_break))
        for stmt in node.body:
            self.visit(stmt)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_head)
        self.loop_stack.pop()

        self.mark_label(lbl_exit)
        if node.orelse:
            for stmt in node.orelse:
                self.visit(stmt)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_end)

        self.mark_label(lbl_break)
        self.mark_label(lbl_end)

    def visit_For(self, node: ast.For):
        self.loop_depth += 1
        iter_slot = self.code_obj.get_local_idx(f'_$iter_{self.loop_depth}')

        lbl_head = self.new_label()
        lbl_break = self.new_label()
        lbl_exit = self.new_label()
        lbl_end = self.new_label()

        self.visit(node.iter)
        self.emit(_TVMOpcodes.GET_ITER)
        self.emit(_TVMOpcodes.STORE_FAST, iter_slot)

        self.mark_label(lbl_head)
        self.emit(_TVMOpcodes.LOAD_FAST, iter_slot)
        self.emit_jump(_TVMOpcodes.FOR_ITER, lbl_exit)

        self._store_target(node.target)

        self.loop_stack.append((lbl_head, lbl_break))
        for stmt in node.body:
            self.visit(stmt)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_head)
        self.loop_stack.pop()

        self.mark_label(lbl_exit)
        if node.orelse:
            for stmt in node.orelse:
                self.visit(stmt)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_end)

        self.mark_label(lbl_break)
        self.mark_label(lbl_end)

        self.loop_depth -= 1

    def visit_AsyncFor(self, node: ast.AsyncFor):
        self.loop_depth += 1
        iter_slot = self.code_obj.get_local_idx(f'_$aiter_{self.loop_depth}')
        pair_slot = self.code_obj.get_local_idx(f'_$anext_pair_{self.loop_depth}')
        ok_slot = self.code_obj.get_local_idx(f'_$anext_ok_{self.loop_depth}')
        val_slot = self.code_obj.get_local_idx(f'_$anext_val_{self.loop_depth}')

        lbl_head = self.new_label()
        lbl_break = self.new_label()
        lbl_exit = self.new_label()
        lbl_end = self.new_label()

        # aiter = await obj.__aiter__()
        self.visit(node.iter)
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('__aiter__'))
        self.emit(_TVMOpcodes.CALL_FUNCTION, 0)
        self.emit(_TVMOpcodes.STORE_FAST, iter_slot)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['await_fn']))
        self.emit(_TVMOpcodes.LOAD_FAST, iter_slot)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        self.emit(_TVMOpcodes.STORE_FAST, iter_slot)

        self.mark_label(lbl_head)
        # (ok, value) = __vm_anext__(aiter)  -- sentinel-free async iteration
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['anext_fn']))
        self.emit(_TVMOpcodes.LOAD_FAST, iter_slot)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        self.emit(_TVMOpcodes.STORE_FAST, pair_slot)
        self.emit(_TVMOpcodes.LOAD_FAST, pair_slot)
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(0))
        self.emit(_TVMOpcodes.GET_ITEM)
        self.emit(_TVMOpcodes.STORE_FAST, ok_slot)
        self.emit(_TVMOpcodes.LOAD_FAST, pair_slot)
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(1))
        self.emit(_TVMOpcodes.GET_ITEM)
        self.emit(_TVMOpcodes.STORE_FAST, val_slot)
        self.emit(_TVMOpcodes.LOAD_FAST, ok_slot)
        self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_exit)

        self.emit(_TVMOpcodes.LOAD_FAST, val_slot)
        self._store_target(node.target)

        self.loop_stack.append((lbl_head, lbl_break))
        for stmt in node.body:
            self.visit(stmt)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_head)
        self.loop_stack.pop()

        self.mark_label(lbl_exit)
        if node.orelse:
            for stmt in node.orelse:
                self.visit(stmt)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_end)

        self.mark_label(lbl_break)
        self.mark_label(lbl_end)

        self.loop_depth -= 1

    def visit_With(self, node: ast.With):
        if len(node.items) > 1:
            inner_with = ast.With(items=node.items[1:], body=node.body)
            single_with = ast.With(items=[node.items[0]], body=[inner_with])
            self.visit(single_with)
            return

        item = node.items[0]
        ctx_slot = self.code_obj.get_local_idx(f'_$ctx_mgr_{self.new_label()}')
        self.visit(item.context_expr)
        self.emit(_TVMOpcodes.STORE_FAST, ctx_slot)

        self.emit(_TVMOpcodes.LOAD_FAST, ctx_slot)
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('__enter__'))
        self.emit(_TVMOpcodes.CALL_FUNCTION, 0)
        if item.optional_vars:
            self._store_target(item.optional_vars)
        else:
            self.emit(_TVMOpcodes.POP_TOP)

        lbl_handler = self.new_label()
        lbl_end = self.new_label()
        lbl_suppressed = self.new_label()

        self.emit_jump(_TVMOpcodes.SETUP_FINALLY, lbl_handler)
        self.exc_frame_depth += 1
        for stmt in node.body:
            self.visit(stmt)
        self.emit(_TVMOpcodes.POP_BLOCK)

        # Normal exit: __exit__(None, None, None)
        self.emit(_TVMOpcodes.LOAD_FAST, ctx_slot)
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('__exit__'))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.CALL_FUNCTION, 3)
        self.emit(_TVMOpcodes.POP_TOP)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_end)

        # Exception exit:
        self.mark_label(lbl_handler)
        exc_slot = self.code_obj.get_local_idx(f'_$with_exc_{self.new_label()}')
        self.emit(_TVMOpcodes.STORE_FAST, exc_slot)

        self.emit(_TVMOpcodes.LOAD_FAST, ctx_slot)
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('__exit__'))

        # Arg 1: type(e)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('type'))
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

        # Arg 2: e
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)

        # Arg 3: getattr(e, '__traceback__', None)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('getattr'))
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx('__traceback__'))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.CALL_FUNCTION, 3)

        self.emit(_TVMOpcodes.CALL_FUNCTION, 3)
        self.emit_jump(_TVMOpcodes.JUMP_IF_TRUE, lbl_suppressed)

        # Re-raise if __exit__ returned falsy
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)
        self.emit(_TVMOpcodes.RAISE_VARARGS)

        self.mark_label(lbl_suppressed)
        self.mark_label(lbl_end)

    def visit_AsyncWith(self, node: ast.AsyncWith):
        if len(node.items) > 1:
            inner_with = ast.AsyncWith(items=node.items[1:], body=node.body)
            single_with = ast.AsyncWith(items=[node.items[0]], body=[inner_with])
            self.visit(single_with)
            return

        item = node.items[0]
        ctx_slot = self.code_obj.get_local_idx(f'_$actx_mgr_{self.new_label()}')
        self.visit(item.context_expr)
        self.emit(_TVMOpcodes.STORE_FAST, ctx_slot)

        self.emit(_TVMOpcodes.LOAD_FAST, ctx_slot)
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('__aenter__'))
        self.emit(_TVMOpcodes.CALL_FUNCTION, 0)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['await_fn']))
        self.emit(_TVMOpcodes.ROT_TWO)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        if item.optional_vars:
            self._store_target(item.optional_vars)
        else:
            self.emit(_TVMOpcodes.POP_TOP)

        lbl_handler = self.new_label()
        lbl_end = self.new_label()
        lbl_suppressed = self.new_label()

        self.emit_jump(_TVMOpcodes.SETUP_FINALLY, lbl_handler)
        self.exc_frame_depth += 1
        for stmt in node.body:
            self.visit(stmt)
        self.emit(_TVMOpcodes.POP_BLOCK)
        self.exc_frame_depth -= 1

        # Normal exit: __aexit__(None, None, None)
        self.emit(_TVMOpcodes.LOAD_FAST, ctx_slot)
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('__aexit__'))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.CALL_FUNCTION, 3)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['await_fn']))
        self.emit(_TVMOpcodes.ROT_TWO)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        self.emit(_TVMOpcodes.POP_TOP)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_end)

        # Exception handler
        self.mark_label(lbl_handler)
        exc_slot = self.code_obj.get_local_idx(f'_$awith_exc_{self.new_label()}')
        self.emit(_TVMOpcodes.STORE_FAST, exc_slot)

        self.emit(_TVMOpcodes.LOAD_FAST, ctx_slot)
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('__aexit__'))

        # Arg 1: type(e)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('type'))
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

        # Arg 2: e
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)

        # Arg 3: getattr(e, '__traceback__', None)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('getattr'))
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx('__traceback__'))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.CALL_FUNCTION, 3)

        self.emit(_TVMOpcodes.CALL_FUNCTION, 3)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['await_fn']))
        self.emit(_TVMOpcodes.ROT_TWO)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

        self.emit_jump(_TVMOpcodes.JUMP_IF_TRUE, lbl_suppressed)

        # Re-raise if __aexit__ returned falsy
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)
        self.emit(_TVMOpcodes.RAISE_VARARGS)

        self.mark_label(lbl_suppressed)
        self.mark_label(lbl_end)

    def visit_Try(self, node: ast.Try):
        has_finally = bool(node.finalbody)
        has_handlers = bool(node.handlers)

        if has_finally:
            lbl_fin_handler = self.new_label()
            lbl_fin_end = self.new_label()
            fin_exc_slot = self.code_obj.get_local_idx(f'_$fin_exc_{self.new_label()}')
            self.emit_jump(_TVMOpcodes.SETUP_FINALLY, lbl_fin_handler)
            self.exc_frame_depth += 1
            self._fin_stack.append(node.finalbody)

        if has_handlers:
            lbl_exc_dispatcher = self.new_label()
            lbl_try_end = self.new_label()

            self.emit_jump(_TVMOpcodes.SETUP_FINALLY, lbl_exc_dispatcher)
            self.exc_frame_depth += 1
            for stmt in node.body:
                self.visit(stmt)
            self.emit(_TVMOpcodes.POP_BLOCK)
            self.exc_frame_depth -= 1

            # Try body succeeded with no exception -> execute orelse
            if node.orelse:
                for stmt in node.orelse:
                    self.visit(stmt)
            self.emit_jump(_TVMOpcodes.JUMP, lbl_try_end)

            # Exception dispatcher
            self.mark_label(lbl_exc_dispatcher)
            for h in node.handlers:
                lbl_next_h = self.new_label()
                if h.type:
                    self.emit(_TVMOpcodes.DUP_TOP)
                    self.visit(h.type)
                    self.emit(_TVMOpcodes.CHECK_EXC_MATCH)
                    self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_next_h)

                if h.name:
                    self.emit(_TVMOpcodes.DUP_TOP)
                    target_node = ast.Name(id=h.name, ctx=ast.Store())
                    self._store_target(target_node)

                self.emit(_TVMOpcodes.POP_TOP)
                for stmt in h.body:
                    self.visit(stmt)
                self.emit_jump(_TVMOpcodes.JUMP, lbl_try_end)

                self.mark_label(lbl_next_h)

            # Re-raise if no handler matched
            self.emit(_TVMOpcodes.RAISE_VARARGS)
            self.mark_label(lbl_try_end)
        else:
            for stmt in node.body:
                self.visit(stmt)

        if has_finally:
            self.emit(_TVMOpcodes.POP_BLOCK)
            self.exc_frame_depth -= 1
            if self._fin_stack: self._fin_stack.pop()
            for stmt in node.finalbody:
                self.visit(stmt)
            self.emit_jump(_TVMOpcodes.JUMP, lbl_fin_end)

            self.mark_label(lbl_fin_handler)
            self.emit(_TVMOpcodes.STORE_FAST, fin_exc_slot)
            for stmt in node.finalbody:
                self.visit(stmt)
            self.emit(_TVMOpcodes.LOAD_FAST, fin_exc_slot)
            self.emit(_TVMOpcodes.RAISE_VARARGS)

            self.mark_label(lbl_fin_end)

    def visit_Break(self, node: ast.Break):
        import copy as _cp2
        for _fb in reversed(self._fin_stack):
            for _fs in _fb:
                self.visit(_cp2.deepcopy(_fs))
        if self.loop_stack:
            _, lbl_break = self.loop_stack[-1]
            for _ in range(self.exc_frame_depth):
                self.emit(_TVMOpcodes.POP_BLOCK)
            self.emit_jump(_TVMOpcodes.JUMP, lbl_break)

    def visit_Continue(self, node: ast.Continue):
        import copy as _cp2
        for _fb in reversed(self._fin_stack):
            for _fs in _fb:
                self.visit(_cp2.deepcopy(_fs))
        if self.loop_stack:
            lbl_head, _ = self.loop_stack[-1]
            for _ in range(self.exc_frame_depth):
                self.emit(_TVMOpcodes.POP_BLOCK)
            self.emit_jump(_TVMOpcodes.JUMP, lbl_head)

    @staticmethod
    def _contains_yield_in_scope(body):
        """True if any Yield/YieldFrom appears directly in this scope
        (does NOT descend into nested function/lambda scopes)."""
        stack = list(body)
        while stack:
            n = stack.pop()
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(n, (ast.Yield, ast.YieldFrom)):
                return True
            for child in ast.iter_child_nodes(n):
                stack.append(child)
        return False

    def visit_Yield(self, node: ast.Yield):
        if getattr(self, 'is_generator', False):
            if node.value:
                self.visit(node.value)
            else:
                self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
            self.emit(_TVMOpcodes.YIELD_VALUE)
        else:
            # yield outside a generator is illegal; keep legacy fallback
            if node.value:
                self.visit(node.value)
            else:
                self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
            self.emit(_TVMOpcodes.RETURN_VALUE)

    def visit_YieldFrom(self, node: ast.YieldFrom):
        # NOTE: CPython itself forbids `yield from` inside async functions
        # (SyntaxError), so only the sync path is reachable for valid sources.
        self.visit(node.value)
        self.emit(_TVMOpcodes.YIELD_FROM)

    def _capture_target(self, name: str) -> ast.Name:
        """Registers a match capture as a proper local (inside functions) and returns a Store target."""
        if self.is_function and name not in self.explicit_globals and name not in self.explicit_nonlocals:
            self.code_obj.get_local_idx(name)
        return ast.Name(id=name, ctx=ast.Store())

    def _match_pattern(self, pat, subj_slot: int, lbl_fail: int):
        """Emits bytecode matching `pat` against the subject held in local slot `subj_slot`.
        Jumps to `lbl_fail` on mismatch; stores capture bindings on success."""
        if isinstance(pat, ast.MatchValue):
            self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
            if isinstance(pat.value, ast.AST):
                self.visit(pat.value)
            else:
                self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(pat.value))
            self.emit(_TVMOpcodes.COMPARE_OP, 2)  # ==
            self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
        elif isinstance(pat, ast.MatchSingleton):
            self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(pat.value))
            self.emit(_TVMOpcodes.COMPARE_OP, 8)  # is
            self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
        elif isinstance(pat, ast.MatchAs):
            if pat.pattern is not None:
                # `case <pattern> as name:` must FIRST match the inner pattern,
                # then bind. The old code skipped the match entirely, so
                # `str() as s` captured any subject (bools, floats, ints...).
                self._match_pattern(pat.pattern, subj_slot, lbl_fail)
            if pat.name is not None:
                self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                self._store_target(self._capture_target(pat.name))
        elif isinstance(pat, ast.MatchClass):
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('isinstance'))
            self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
            self.visit(pat.cls)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 2)
            self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
            # FIX (GAP-35): missing kwd attr must FAIL the pattern (CPython),
            # not raise AttributeError through user code. getattr-3-arg +
            # _NO_ARG sentinel comparison.
            _no_arg_gi = self.code_obj.get_name_idx(_TVM_TOKENS['no_arg'])
            for attr_name, kp_node in zip(pat.kwd_attrs, pat.kwd_patterns):
                self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('getattr'))
                self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(attr_name))
                self.emit(_TVMOpcodes.LOAD_GLOBAL, _no_arg_gi)
                self.emit(_TVMOpcodes.CALL_FUNCTION, 3)
                tmp_slot = self.code_obj.get_local_idx(f'_$mk_{self.new_label()}')
                self.emit(_TVMOpcodes.STORE_FAST, tmp_slot)
                self.emit(_TVMOpcodes.LOAD_FAST, tmp_slot)
                self.emit(_TVMOpcodes.LOAD_GLOBAL, _no_arg_gi)
                self.emit(_TVMOpcodes.COMPARE_OP, 9)  # is not
                self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
                self._match_pattern(kp_node, tmp_slot, lbl_fail)
            if pat.patterns:
                if len(pat.patterns) == 1 and isinstance(pat.patterns[0], ast.MatchAs):
                    cap = pat.patterns[0]
                    if cap.name is not None:
                        self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                        self._store_target(self._capture_target(cap.name))
                else:
                    _ma_gi = self.code_obj.get_name_idx('__tvm_margs')
                    for p_idx, pp_node in enumerate(pat.patterns):
                        # FIX (GAP-35b): positional index beyond __match_args__
                        # must fail the pattern, not raise IndexError.
                        self.emit(_TVMOpcodes.LOAD_GLOBAL, _ma_gi)
                        self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                        self.visit(pat.cls)
                        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(p_idx))
                        self.emit(_TVMOpcodes.CALL_FUNCTION, 3)
                        tmp_slot = self.code_obj.get_local_idx(f'_$mk_{self.new_label()}')
                        self.emit(_TVMOpcodes.STORE_FAST, tmp_slot)
                        self.emit(_TVMOpcodes.LOAD_FAST, tmp_slot)
                        self.emit(_TVMOpcodes.LOAD_GLOBAL, _no_arg_gi)
                        self.emit(_TVMOpcodes.COMPARE_OP, 9)  # is not
                        self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
                        self._match_pattern(pp_node, tmp_slot, lbl_fail)
        elif isinstance(pat, ast.MatchMapping):
            # FIX (GAP-34): match ANY collections.abc.Mapping (os.environ,
            # defaultdict, MappingProxyType...), not only exact dict.
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('__tvm_is_map'))
            self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
            self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
            for key_node, pat_node in zip(pat.keys, pat.patterns):
                self.visit(key_node)
                self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                self.emit(_TVMOpcodes.COMPARE_OP, 6)  # in
                self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
                self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                self.visit(key_node)
                self.emit(_TVMOpcodes.GET_ITEM)
                tmp_slot = self.code_obj.get_local_idx(f'_$mm_{self.new_label()}')
                self.emit(_TVMOpcodes.STORE_FAST, tmp_slot)
                self._match_pattern(pat_node, tmp_slot, lbl_fail)
            if pat.rest is not None:
                self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['match_rest']))
                self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                for key_node in pat.keys:
                    self.visit(key_node)
                self.emit(_TVMOpcodes.BUILD_TUPLE, len(pat.keys))
                self.emit(_TVMOpcodes.CALL_FUNCTION, 2)
                self._store_target(self._capture_target(pat.rest))
        elif isinstance(pat, ast.MatchSequence):
            has_star = any(isinstance(p, ast.MatchStar) for p in pat.patterns)
            # FIX (GAP-33): CPython sequence patterns match ANY object with
            # __len__/__getitem__ (range, deque, array, numpy 1-D...) except
            # str/bytes/bytearray. Use a runtime protocol helper instead of an
            # exact (tuple, list) isinstance that silently skipped custom containers.
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('__tvm_is_seq'))
            self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
            self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('len'))
            self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(len(pat.patterns)))
            if has_star:
                self.emit(_TVMOpcodes.COMPARE_OP, 5)  # >=
            else:
                self.emit(_TVMOpcodes.COMPARE_OP, 2)  # ==
            self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
            for p_idx, p_node in enumerate(pat.patterns):
                if isinstance(p_node, ast.MatchStar):
                    if p_node.name is not None:
                        n_after = len(pat.patterns) - p_idx - 1
                        upper_val = None if n_after == 0 else -n_after
                        self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(p_idx))
                        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(upper_val))
                        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
                        self.emit(_TVMOpcodes.BUILD_SLICE, 3)
                        self.emit(_TVMOpcodes.GET_ITEM)
                        self._store_target(self._capture_target(p_node.name))
                else:
                    self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                    self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(p_idx))
                    self.emit(_TVMOpcodes.GET_ITEM)
                    tmp_slot = self.code_obj.get_local_idx(f'_$ms_{self.new_label()}')
                    self.emit(_TVMOpcodes.STORE_FAST, tmp_slot)
                    self._match_pattern(p_node, tmp_slot, lbl_fail)
        elif isinstance(pat, ast.MatchOr):
            # FIX (GAP-36): a partially-matched alternative must NOT leave its
            # captures installed when it fails. Snapshot every capture slot the
            # alternatives can write, restore on failure.
            cap_slots = []
            def _collect_caps(p):
                for ch in ast.walk(p):
                    if isinstance(ch, ast.MatchAs) and ch.name:
                        cap_slots.append(self._capture_target(ch.name).id)
                    elif isinstance(ch, ast.MatchStar) and ch.name:
                        cap_slots.append(self._capture_target(ch.name).id)
                    elif isinstance(ch, ast.MatchMapping) and ch.rest:
                        cap_slots.append(self._capture_target(ch.rest).id)
            for alt in pat.patterns:
                _collect_caps(alt)
            uniq_slots = list(dict.fromkeys(cap_slots))
            snap_slot = self.code_obj.get_local_idx(f'_$orsnap_{self.new_label()}')
            # snapshot current values of every possible capture binding
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('__tvm_snap'))
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(tuple(uniq_slots)))
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
            self.emit(_TVMOpcodes.STORE_FAST, snap_slot)
            lbl_ok = self.new_label()
            for alt in pat.patterns:
                lbl_alt_fail = self.new_label()
                self._match_pattern(alt, subj_slot, lbl_alt_fail)
                self.emit_jump(_TVMOpcodes.JUMP, lbl_ok)
                self.mark_label(lbl_alt_fail)
            # all failed -> rollback captures then fail upward
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('__tvm_restore'))
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(tuple(uniq_slots)))
            self.emit(_TVMOpcodes.LOAD_FAST, snap_slot)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 2)
            self.emit(_TVMOpcodes.POP_TOP)
            self.emit_jump(_TVMOpcodes.JUMP, lbl_fail)
            self.mark_label(lbl_ok)
        # Unknown/unsupported pattern kinds: emit no constraint (always matches).

    def visit_Match(self, node: ast.Match):
        lbl_match_end = self.new_label()
        self.visit(node.subject)
        subj_slot = self.code_obj.get_local_idx(f'_$subj_{self.new_label()}')
        self.emit(_TVMOpcodes.STORE_FAST, subj_slot)

        for case_clause in node.cases:
            lbl_next_case = self.new_label()
            self._match_pattern(case_clause.pattern, subj_slot, lbl_next_case)

            if case_clause.guard:
                self.visit(case_clause.guard)
                self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_next_case)

            for stmt in case_clause.body:
                self.visit(stmt)
            self.emit_jump(_TVMOpcodes.JUMP, lbl_match_end)
            self.mark_label(lbl_next_case)

        self.mark_label(lbl_match_end)

    def visit_Return(self, node: ast.Return):
        if self._fin_stack:
            ret_slot = self.code_obj.get_local_idx(f'_$ret_val_{self.new_label()}')
            if node.value:
                self.visit(node.value)
            else:
                self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
            self.emit(_TVMOpcodes.STORE_FAST, ret_slot)
            import copy as _cp
            for _fb in reversed(self._fin_stack):
                for _fs in _fb:
                    self.visit(_cp.deepcopy(_fs))
            self.emit(_TVMOpcodes.LOAD_FAST, ret_slot)
        else:
            if node.value:
                self.visit(node.value)
            else:
                self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.RETURN_VALUE)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            idx = self.code_obj.get_name_idx(alias.name)
            self.emit(_TVMOpcodes.IMPORT_NAME, idx)
            if alias.asname:
                # `import a.b as c` must bind c = a.b (the submodule), not a.
                # FIX (GAP-30): route through the fromlist sentinel so the
                # SUBMODULE is returned directly - the old IMPORT_NAME(root)
                # + IMPORT_FROM(sub) + POP_TOP sequence popped the WRONG item
                # and bound the root package to the alias.
                if '.' in alias.name:
                    last_part = alias.name.split('.')[-1]
                    fl_sentinel = _TVM_TOKENS['fl_prefix'] + alias.name + '\x00' + last_part
                    idx = self.code_obj.get_name_idx(fl_sentinel)
                    self.emit(_TVMOpcodes.IMPORT_NAME, idx)
                target_name = alias.asname
            else:
                # plain `import a.b` binds the root package 'a'
                target_name = alias.name.split('.')[0]
            store_idx = self.code_obj.get_name_idx(target_name)
            self.emit(_TVMOpcodes.STORE_GLOBAL, store_idx)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        # FIX (GAP-31): star + relative imports are unsupported by the VM
        # runtime; previously they crashed at RUNTIME with opaque errors.
        # Fail LOUD at compile time instead.
        if any(alias.name == '*' for alias in node.names):
            raise TVMEmitError("from-module import * is not supported by TVM virtualization")
        if node.level and node.level > 0:
            raise TVMEmitError("relative imports are not supported by TVM virtualization")
        # FIX (GAP-29): `from pkg.sub import name` previously called
        # __import__('pkg.sub') WITHOUT fromlist -> returned the ROOT package
        # -> getattr failed. The handler recognizes this sentinel name form
        # and re-imports with fromlist so the SUBMODULE is returned.
        names_csv = ','.join(a.name for a in node.names)
        sentinel = _TVM_TOKENS['fl_prefix'] + (node.module or '') + '\x00' + names_csv
        mod_idx = self.code_obj.get_name_idx(sentinel)
        self.emit(_TVMOpcodes.IMPORT_NAME, mod_idx)
        for alias in node.names:
            attr_idx = self.code_obj.get_name_idx(alias.name)
            self.emit(_TVMOpcodes.IMPORT_FROM, attr_idx)
            target_name = alias.asname or alias.name
            store_idx = self.code_obj.get_name_idx(target_name)
            self.emit(_TVMOpcodes.STORE_GLOBAL, store_idx)
        self.emit(_TVMOpcodes.POP_TOP)

    def finalize(self) -> _TVMCodeObject:
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.RETURN_VALUE)

        if self.vm_level >= 2:
            old_insts = self.code_obj.instructions
            new_insts = []
            target_pos_map = {}
            inst_pos_map = {}
            for old_idx, (op, arg) in enumerate(old_insts):
                target_pos_map[old_idx] = len(new_insts)
                # Level 2 & 3: Randomized NOP insertion
                if self.rng.random() < 0.15:
                    new_insts.append((_TVMOpcodes.NOP, 0))
                # Level 3: Dummy Invariant Push/Pop cycle insertion
                if self.vm_level >= 3 and self.rng.random() < 0.10:
                    d_idx = self.code_obj.get_const_idx(0)
                    new_insts.append((_TVMOpcodes.LOAD_CONST, d_idx))
                    new_insts.append((_TVMOpcodes.POP_TOP, 0))
                inst_pos_map[old_idx] = len(new_insts)
                new_insts.append((op, arg))
                # After unconditional exits, insert unreachable Dead Traps
                if op in (_TVMOpcodes.RETURN_VALUE, _TVMOpcodes.HALT, _TVMOpcodes.RAISE_VARARGS):
                    num_traps = self.rng.randint(1, 3)
                    for _ in range(num_traps):
                        new_insts.append((_TVMOpcodes.TRAP, self.rng.randint(0, 65535)))

            target_pos_map[len(old_insts)] = len(new_insts)
            inst_pos_map[len(old_insts)] = len(new_insts)
            self.labels = {lbl_id: target_pos_map.get(old_t, len(new_insts) - 1) for lbl_id, old_t in self.labels.items()}
            self.label_fixups = {lbl_id: [inst_pos_map.get(old_f, 0) for old_f in fix_list] for lbl_id, fix_list in self.label_fixups.items()}
            self.code_obj.instructions = new_insts

        for lbl_id, fixup_indices in self.label_fixups.items():
            target_ip = self.labels.get(lbl_id, len(self.code_obj.instructions) - 1)
            for fix_idx in fixup_indices:
                op, _ = self.code_obj.instructions[fix_idx]
                self.code_obj.instructions[fix_idx] = (op, target_ip)
        return self.code_obj


_TVM_MAGIC = b"TVM1"
_TVM_VERSION = 4

# Tamper response modes for the emitted runtime.
#   'exit'   - process terminates on any integrity failure (default)
#   'poison' - keys are silently degraded and execution continues inert
_TVM_TAMPER_MODES = ("exit", "poison")


def _tvm_derive_runtime_keys(seed_bytes: bytes, salt_bytes: bytes = b'') -> Tuple[bytes, bytes]:
    """
    Derives dynamic cryptographic keystream and HMAC keys using iterative SHA-256 expansion with domain separation.
    Returns (k_enc, k_mac).
    """
    k_enc = hashlib.sha256(b"TRX_TVM_ENC_KEY_V3:" + seed_bytes + salt_bytes).digest()
    k_mac = hashlib.sha256(b"TRX_TVM_MAC_KEY_V3:" + seed_bytes + salt_bytes).digest()
    return k_enc, k_mac


def _tvm_aead_encrypt(payload: bytes, k_enc: bytes, k_mac: bytes) -> bytes:
    """
    Encrypts payload using counter-mode keystream XOR + HMAC-SHA256 authenticated envelope.
    Envelope format: [Nonce: 16B] + [HMAC Tag: 32B] + [Ciphertext: NB]
    """
    nonce = secrets.token_bytes(16)
    plen = len(payload)
    num_blocks = (plen + 31) // 32
    ks = bytearray()
    for i in range(num_blocks):
        ctr = i.to_bytes(4, 'big')
        ks.extend(hashlib.sha256(k_enc + nonce + ctr).digest())
    ciphertext = bytes(p ^ k for p, k in zip(payload, ks[:plen]))
    tag = hmac.new(k_mac, nonce + ciphertext, hashlib.sha256).digest()
    return nonce + tag + ciphertext


def _serialize_tvm_code_object(code: _TVMCodeObject, isa_map: Dict[int, int], k_enc: bytes, k_mac: bytes, perm_get=None) -> bytes:
    """
    Recursively serializes a _TVMCodeObject and nested code objects into an authenticated AEAD structure.
    Nested code objects inside constants are encrypted with unique child salts and stored as lazy records.
    perm_get(name) -> optional per-code-object substitution list applied AFTER isa_map
    (level-4 per-function ISA divergence).
    """
    inv = perm_get(code.name) if perm_get else None
    bytecode_ba = bytearray()
    for op, arg in code.instructions:
        mapped_op = isa_map.get(op, op)
        if inv is not None:
            mapped_op = inv[mapped_op & 0xFF]
        bytecode_ba.append(mapped_op & 0xFF)
        bytecode_ba.append((arg >> 8) & 0xFF)
        bytecode_ba.append(arg & 0xFF)

    serialized_consts = []
    for c in code.constants:
        if isinstance(c, _TVMCodeObject):
            child_salt = secrets.token_bytes(16)
            child_k_enc, child_k_mac = _tvm_derive_runtime_keys(k_enc, child_salt)
            child_encrypted = _serialize_tvm_code_object(c, isa_map, child_k_enc, child_k_mac, perm_get)
            serialized_consts.append((_TVM_TOKENS['lazy'], child_salt, child_encrypted))
        else:
            serialized_consts.append(c)

    raw_payload = marshal.dumps((
        code.name,
        code.arg_names,
        getattr(code, 'kwonly_names', []),
        code.vararg_name,
        code.kwarg_name,
        code.local_names,
        bytes(bytecode_ba),
        tuple(serialized_consts),
        tuple(code.names),
        tuple(getattr(code, 'kwonly_default_names', ())),
        # PERF G2: indexes of names that are certain-globals (declared `global`)
        tuple(sorted(getattr(code, 'global_only_idx', ()) or ()))
    ))

    import zlib as _zlib_mod
    compressed_payload = _zlib_mod.compress(raw_payload, level=9)
    return _tvm_aead_encrypt(compressed_payload, k_enc, k_mac)


def _vm_emit_runtime_interpreter_v2(root_code: _TVMCodeObject, isa_map: Dict[int, int], vm_level: int, rng: random.Random, vm_debug: bool = False) -> str:
    """Emits the pure Python Polymorphic Virtual Machine Runtime Interpreter 2.0 with AEAD decryption and dynamic affine dispatch."""
    # Deterministic per-name 256-byte permutation (level 4 ISA divergence).
    def _perm_from_seed(name: str, seed: bytes):
        import hashlib as _hlib
        data = b"TRX_PERM:" + seed + name.encode('utf-8', 'replace')
        perm = list(range(256))
        i = 255
        counter = 0
        while i > 0:
            blk = _hlib.sha256(data + counter.to_bytes(4, 'big')).digest()
            counter += 1
            for b in blk:
                if i == 0:
                    break
                j = b % (i + 1)
                perm[i], perm[j] = perm[j], perm[i]
                i -= 1
        return perm

    master_seed = secrets.token_bytes(32)
    runtime_salt = secrets.token_bytes(16)
    k_enc, k_mac = _tvm_derive_runtime_keys(master_seed, runtime_salt)

    if vm_level >= 4 and getattr(__import__('os').environ.get('TRX_VM_L4_PERM', '0'), '__class__', str) is not type:
        pass  # placeholder keeps linters calm

    if vm_level >= 4 and os.environ.get("TRX_VM_L4_PERM") == "1":
        _perm_cache = {}

        def _perm_inv_for(name: str):
            p = _perm_cache.get(name)
            if p is None:
                fwd = _perm_from_seed(name, master_seed)
                inv = [0] * 256
                for stored, mapped in enumerate(fwd):
                    inv[mapped] = stored
                p = (fwd, inv)
                _perm_cache[name] = p
            return p

        def _perm_get(name: str):
            return _perm_inv_for(name)[1]
    else:
        def _perm_get(name: str):
            return None

    serialized_root_packet = _serialize_tvm_code_object(root_code, isa_map, k_enc, k_mac, _perm_get)

    v = {k: rd() for k in [
        'code_obj_cls', 'frame_cls', 'interp_fn', 'call_vm_fn', 'eval_frame_fn',
        'eval_frame_async_fn', 'call_vm_async_fn', 'lazy_decode_fn',
        'derive_keys_fn', 'decrypt_packet_fn', 'decode_code_fn',
        'root_packet', 'master_seed', 'runtime_salt', 'dispatch_tbl',
        'dispatch_tbl_async', 'ret_sig', 'await_sig', 'halt_sig',
        'yield_sig', 'no_arg_sig', 'active_frames', 'vm_super_fn', 'vm_await_fn',
        'vm_anext_fn', 'bind_frame_fn', 'gen_cls', 'agen_cls', 'async_depth',
        'attach_isa_fn', 'perm_rt_fn',
        'trap_fn', 'env_chain_cls'
    ]}

    # Level-4 per-function ISA divergence is implemented (serializer + runtime
    # inverse-dispatch) but DISABLED pending a unique-per-code-object salt:
    # keying the permutation by bare name let same-named code objects share a
    # mapping, which produced cross-frame semantic subtleties. Flip once isa
    # salts are threaded through serialization.
    _TVM_L4_PERM_ENABLED = False

    odd_multipliers = [m for m in range(3, 256, 2)]
    M = rng.choice(odd_multipliers)
    _trap_delay = round(rng.uniform(0.01, 0.15), 4)
    A = rng.randint(0, 255)
    tok = _TVM_TOKENS

    _DBG_AE = "pass"
    _DBG_CALLA = "pass"
    if vm_debug:
        _DBG_AE = ("import sys as _vdbg\n        "
                   f"_vdbg.stderr.write('AE+ depth=%r\\n' % ({v['async_depth']}[0]))")
        _DBG_CALLA = ("import sys as _vdbg2\n        "
                      f"_vdbg2.stderr.write('CALLA fn=%r depth=%r\\n' % (getattr(_fn, '__name__', '?'), {v['async_depth']}[0]))")

    def affine_slot(std_op: int) -> int:
        mapped_op = isa_map.get(std_op, std_op)
        return (mapped_op * M + A) % 256

    slot_ld_c    = affine_slot(_TVMOpcodes.LOAD_CONST)
    slot_ld_g    = affine_slot(_TVMOpcodes.LOAD_GLOBAL)
    slot_st_g    = affine_slot(_TVMOpcodes.STORE_GLOBAL)
    slot_ld_f    = affine_slot(_TVMOpcodes.LOAD_FAST)
    slot_st_f    = affine_slot(_TVMOpcodes.STORE_FAST)
    slot_dup     = affine_slot(_TVMOpcodes.DUP_TOP)
    slot_pop     = affine_slot(_TVMOpcodes.POP_TOP)
    slot_rot2    = affine_slot(_TVMOpcodes.ROT_TWO)
    slot_rot3    = affine_slot(_TVMOpcodes.ROT_THREE)

    slot_add     = affine_slot(_TVMOpcodes.BINARY_ADD)
    slot_sub     = affine_slot(_TVMOpcodes.BINARY_SUB)
    slot_mul     = affine_slot(_TVMOpcodes.BINARY_MUL)
    slot_div     = affine_slot(_TVMOpcodes.BINARY_DIV)
    slot_fdiv    = affine_slot(_TVMOpcodes.BINARY_FLOORDIV)
    slot_mod     = affine_slot(_TVMOpcodes.BINARY_MOD)
    slot_pow     = affine_slot(_TVMOpcodes.BINARY_POW)
    slot_and     = affine_slot(_TVMOpcodes.BINARY_AND)
    slot_or      = affine_slot(_TVMOpcodes.BINARY_OR)
    slot_xor     = affine_slot(_TVMOpcodes.BINARY_XOR)
    slot_lsh     = affine_slot(_TVMOpcodes.BINARY_LSHIFT)
    slot_rsh     = affine_slot(_TVMOpcodes.BINARY_RSHIFT)
    slot_neg     = affine_slot(_TVMOpcodes.UNARY_NEG)
    slot_not     = affine_slot(_TVMOpcodes.UNARY_NOT)
    slot_inv     = affine_slot(_TVMOpcodes.UNARY_INVERT)
    slot_matmul  = affine_slot(_TVMOpcodes.BINARY_MATMUL)

    slot_cmp     = affine_slot(_TVMOpcodes.COMPARE_OP)

    slot_jmp     = affine_slot(_TVMOpcodes.JUMP)
    slot_jmp_t   = affine_slot(_TVMOpcodes.JUMP_IF_TRUE)
    slot_jmp_f   = affine_slot(_TVMOpcodes.JUMP_IF_FALSE)
    slot_jmp_f_p = affine_slot(_TVMOpcodes.JUMP_IF_FALSE_OR_POP)
    slot_jmp_t_p = affine_slot(_TVMOpcodes.JUMP_IF_TRUE_OR_POP)
    slot_ret     = affine_slot(_TVMOpcodes.RETURN_VALUE)

    slot_g_attr  = affine_slot(_TVMOpcodes.GET_ATTR)
    slot_s_attr  = affine_slot(_TVMOpcodes.SET_ATTR)
    slot_d_attr  = affine_slot(_TVMOpcodes.DEL_ATTR)
    slot_g_item  = affine_slot(_TVMOpcodes.GET_ITEM)
    slot_s_item  = affine_slot(_TVMOpcodes.SET_ITEM)
    slot_d_item  = affine_slot(_TVMOpcodes.DEL_ITEM)
    slot_d_fast  = affine_slot(_TVMOpcodes.DEL_FAST)
    slot_d_glob  = affine_slot(_TVMOpcodes.DEL_GLOBAL)

    slot_b_list  = affine_slot(_TVMOpcodes.BUILD_LIST)
    slot_b_tup   = affine_slot(_TVMOpcodes.BUILD_TUPLE)
    slot_b_set   = affine_slot(_TVMOpcodes.BUILD_SET)
    slot_b_dict  = affine_slot(_TVMOpcodes.BUILD_DICT)
    slot_unp_seq = affine_slot(_TVMOpcodes.UNPACK_SEQUENCE)
    slot_unp_ex  = affine_slot(_TVMOpcodes.UNPACK_EX)
    slot_b_slice = affine_slot(_TVMOpcodes.BUILD_SLICE)

    slot_mk_fn   = affine_slot(_TVMOpcodes.MAKE_FUNCTION)
    slot_call_fn = affine_slot(_TVMOpcodes.CALL_FUNCTION)
    slot_call_kw = affine_slot(_TVMOpcodes.CALL_FUNCTION_KW)
    slot_call_ex = affine_slot(_TVMOpcodes.CALL_FUNCTION_EX)
    slot_b_cls   = affine_slot(_TVMOpcodes.BUILD_CLASS)
    slot_imp_n   = affine_slot(_TVMOpcodes.IMPORT_NAME)
    slot_imp_f   = affine_slot(_TVMOpcodes.IMPORT_FROM)
    slot_ld_drf  = affine_slot(_TVMOpcodes.LOAD_DEREF)
    slot_st_drf  = affine_slot(_TVMOpcodes.STORE_DEREF)

    slot_g_iter  = affine_slot(_TVMOpcodes.GET_ITER)
    slot_for_it  = affine_slot(_TVMOpcodes.FOR_ITER)
    slot_st_fin  = affine_slot(_TVMOpcodes.SETUP_FINALLY)
    slot_pop_blk = affine_slot(_TVMOpcodes.POP_BLOCK)
    slot_raise   = affine_slot(_TVMOpcodes.RAISE_VARARGS)
    slot_chk_exc = affine_slot(_TVMOpcodes.CHECK_EXC_MATCH)

    slot_halt    = affine_slot(_TVMOpcodes.HALT)
    slot_nop     = affine_slot(_TVMOpcodes.NOP)
    slot_trap    = affine_slot(_TVMOpcodes.TRAP)
    slot_yield   = affine_slot(_TVMOpcodes.YIELD_VALUE)
    slot_yfrom   = affine_slot(_TVMOpcodes.YIELD_FROM)

    reg_entries = [
        (slot_ld_c, '_h_ld_c'),
        (slot_ld_g, '_h_ld_g'),
        (slot_st_g, '_h_st_g'),
        (slot_ld_f, '_h_ld_f'),
        (slot_st_f, '_h_st_f'),
        (slot_dup, '_h_dup'),
        (slot_pop, '_h_pop'),
        (slot_rot2, '_h_rot2'),
        (slot_rot3, '_h_rot3'),
        (slot_add, '_h_add'),
        (slot_sub, '_h_sub'),
        (slot_mul, '_h_mul'),
        (slot_div, '_h_div'),
        (slot_fdiv, '_h_fdiv'),
        (slot_mod, '_h_mod'),
        (slot_pow, '_h_pow'),
        (slot_and, '_h_and'),
        (slot_or, '_h_or'),
        (slot_xor, '_h_xor'),
        (slot_lsh, '_h_lsh'),
        (slot_rsh, '_h_rsh'),
        (slot_neg, '_h_neg'),
        (slot_not, '_h_not'),
        (slot_inv, '_h_inv'),
        (slot_matmul, '_h_matmul'),
        (slot_cmp, '_h_cmp'),
        (slot_jmp, '_h_jmp'),
        (slot_jmp_t, '_h_jmp_t'),
        (slot_jmp_f, '_h_jmp_f'),
        (slot_jmp_f_p, '_h_jmp_f_p'),
        (slot_jmp_t_p, '_h_jmp_t_p'),
        (slot_ret, '_h_ret'),
        (slot_g_attr, '_h_g_attr'),
        (slot_s_attr, '_h_s_attr'),
        (slot_d_attr, '_h_d_attr'),
        (slot_g_item, '_h_g_item'),
        (slot_s_item, '_h_s_item'),
        (slot_d_item, '_h_d_item'),
        (slot_d_fast, '_h_d_fast'),
        (slot_d_glob, '_h_d_glob'),
        (slot_b_list, '_h_b_list'),
        (slot_b_tup, '_h_b_tup'),
        (slot_b_set, '_h_b_set'),
        (slot_b_dict, '_h_b_dict'),
        (slot_unp_seq, '_h_unp_seq'),
        (slot_unp_ex, '_h_unp_ex'),
        (slot_b_slice, '_h_b_slice'),
        (slot_mk_fn, '_h_mk_fn'),
        (slot_call_fn, '_h_call_fn'),
        (slot_call_kw, '_h_call_kw'),
        (slot_call_ex, '_h_call_ex'),
        (slot_b_cls, '_h_b_cls'),
        (slot_imp_n, '_h_imp_n'),
        (slot_imp_f, '_h_imp_f'),
        (slot_ld_drf, '_h_ld_drf'),
        (slot_st_drf, '_h_st_drf'),
        (slot_g_iter, '_h_g_iter'),
        (slot_for_it, '_h_for_it'),
        (slot_st_fin, '_h_st_fin'),
        (slot_pop_blk, '_h_pop_blk'),
        (slot_raise, '_h_raise'),
        (slot_chk_exc, '_h_chk_exc'),
        (slot_nop, '_h_nop'),
        (slot_halt, '_h_halt'),
        (slot_trap, v['trap_fn']),
        (slot_yield, '_h_yield'),
        (slot_yfrom, '_h_yield_from')
    ]
    rng.shuffle(reg_entries)
    reg_stmts = "\n    ".join([f"{v['dispatch_tbl']}[{s}] = {fn}; {v['dispatch_tbl_async']}[{s}] = {fn}" for s, fn in reg_entries])

    src = f"""
def {v['interp_fn']}(_root_packet, _master_seed, _runtime_salt):
    import hashlib as _hashlib
    import hmac as _hmac
    import marshal as _marshal
    import os as _os
    import sys as _sys
    import zlib as _zlib
    _sys_len = len

    # PERF G1: snapshot the interpreter's long-lived objects out of the GC
    # generational scans after the initial load; artifact workloads create
    # mostly short-lived frames/stacks afterwards.
    try:
        import gc as _trx_gc
        _trx_gc.collect()
        _trx_gc.freeze()
    except Exception:
        pass

    if hasattr(_sys, 'monitoring'):
        try:
            _ttag = 'tx' + _hashlib.sha256(_root_packet[:9]).hexdigest()[:6]
            for _tool_id in range(6):
                try:
                    if _sys.monitoring.get_tool(_tool_id) is None:
                        try:
                            _sys.monitoring.use_tool_id(_tool_id, _ttag)
                            _sys.monitoring.set_events(_tool_id, 0)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    def {v['derive_keys_fn']}(_seed, _salt=b''):
        _k1 = _hashlib.sha256(b"TRX_TVM_ENC_KEY_V3:" + _seed + _salt).digest()
        _k2 = _hashlib.sha256(b"TRX_TVM_MAC_KEY_V3:" + _seed + _salt).digest()
        return _k1, _k2

    def {v['decrypt_packet_fn']}(_packet, _k_enc, _k_mac):
        if _sys_len(_packet) < 48:
            _os._exit(1)
        _nonce = _packet[:16]
        _tag = _packet[16:48]
        _ciphertext = _packet[48:]
        _expected_tag = _hmac.new(_k_mac, _nonce + _ciphertext, _hashlib.sha256).digest()
        if not _hmac.compare_digest(_tag, _expected_tag):
            _os._exit(1)
        _plen = _sys_len(_ciphertext)
        _num_blocks = (_plen + 31) // 32
        _ks = bytearray()
        for _i in range(_num_blocks):
            _ctr = _i.to_bytes(4, 'big')
            _ks.extend(_hashlib.sha256(_k_enc + _nonce + _ctr).digest())
        return bytes(_c ^ _k for _c, _k in zip(_ciphertext, _ks[:_plen]))

    def {v['decode_code_fn']}(_packet, _k_enc, _k_mac):
        _compressed_bytes = {v['decrypt_packet_fn']}(_packet, _k_enc, _k_mac)
        _raw_bytes = _zlib.decompress(_compressed_bytes)
        _data = _marshal.loads(_raw_bytes)
        return {v['code_obj_cls']}(_data, _k_enc)

    class {v['code_obj_cls']}:
        def __init__(self, data, parent_k_enc):
            self.name = data[0]
            self.arg_names = data[1]
            self.kwonly_names = data[2]
            self.vararg_name = data[3]
            self.kwarg_name = data[4]
            self.local_names = data[5]
            self.code = data[6]
            self.constants = list(data[7])
            self.names = data[8]
            self.kwonly_default_names = tuple(data[9]) if _sys_len(data) > 9 else ()
            # PERF G2: certain-global name indexes (skip frames-walk in ld_g)
            self.global_only = frozenset(data[10]) if _sys_len(data) > 10 else ()
            self.defining_class = None
            self._k_enc = parent_k_enc

        def resolve_const(self, idx):
            c = self.constants[idx]
            if isinstance(c, tuple) and _sys_len(c) == 3 and c[0] == {repr(tok['lazy'])}:
                child_salt, child_packet = c[1], c[2]
                child_k_enc, child_k_mac = {v['derive_keys_fn']}(self._k_enc, child_salt)
                decoded = {v['decode_code_fn']}(child_packet, child_k_enc, child_k_mac)
                self.constants[idx] = decoded
                return decoded
            return c

    class {v['frame_cls']}:
        def __init__(self, code_obj, locals_dict, global_env):
            self.code_obj = code_obj
            self.pc = 0
            self.stack = []
            self.locals = locals_dict
            self.global_env = global_env
            self.exc_handlers = []
            self.current_exception = None
            self.captured_env = None
            self.defining_class = None
            self.is_generator = False
            self.just_resumed = False
            self.dele = None
            self.injected_exc = None
            self._m = 1
            self._a = 0

    def {v['lazy_decode_fn']}(c, parent_k_enc=None):
        if isinstance(c, tuple) and _sys_len(c) == 3 and c[0] == {repr(tok['lazy'])}:
            child_salt, child_packet = c[1], c[2]
            child_k_enc, child_k_mac = {v['derive_keys_fn']}(parent_k_enc or _root_k_enc, child_salt)
            return {v['decode_code_fn']}(child_packet, child_k_enc, child_k_mac)
        return c

    _root_k_enc, _root_k_mac = {v['derive_keys_fn']}(_master_seed, _runtime_salt)
    _root_code = {v['decode_code_fn']}(_root_packet, _root_k_enc, _root_k_mac)

    _g_env = globals()
    {v['active_frames']} = []
    {v['no_arg_sig']} = object()
    _g_env[{repr(tok['no_arg'])}] = {v['no_arg_sig']}
    {v['ret_sig']} = object()
    {v['await_sig']} = object()
    {v['yield_sig']} = object()
    {v['halt_sig']} = object()
    {v['async_depth']} = [0]

    def {v['perm_rt_fn']}(_nm, _sd):
        _data = b"TRX_PERM:" + _sd + _nm.encode('utf-8', 'replace')
        _perm = list(range(256))
        _i = 255
        _ctr = 0
        while _i > 0:
            _blk = _hashlib.sha256(_data + _ctr.to_bytes(4, 'big')).digest()
            _ctr += 1
            for _b in _blk:
                if _i == 0:
                    break
                _j = _b % (_i + 1)
                _perm[_i], _perm[_j] = _perm[_j], _perm[_i]
                _i -= 1
        return _perm

    def {v['trap_fn']}(_f, _a):
        import time as _tm
        _tm.sleep({_trap_delay})
        _os._exit(1)

    # Live closure environment chain (closure cell semantics). Delegates to the
    # defining frames' real locals dicts instead of snapshot copies, so nonlocal
    # writes stay visible across sibling closures and after frame return.
    # Sentinel-transparency: unfilled binder slots hold {v['no_arg_sig']} and
    # must read as ABSENT (native UnboundLocalError semantics), otherwise a
    # child comprehension/function can observe a bare sentinel value.
    class {v['env_chain_cls']}:
        __slots__ = ('_own', '_parent')
        def __init__(self, _o, _p):
            self._own = _o
            self._parent = _p
        def __contains__(self, k):
            if k in self._own and self._own[k] is not {v['no_arg_sig']}:
                return True
            return self._parent is not None and k in self._parent
        def __getitem__(self, k):
            if k in self._own and self._own[k] is not {v['no_arg_sig']}:
                return self._own[k]
            if self._parent is not None:
                return self._parent[k]
            raise KeyError(k)
        def __setitem__(self, k, val):
            if k in self._own:
                self._own[k] = val
            elif self._parent is not None and k in self._parent:
                self._parent[k] = val
            else:
                self._own[k] = val
        def get(self, k, d=None):
            try:
                return self[k]
            except KeyError:
                return d

    # Dynamic Opcode Handlers
    def _h_ld_c(_f, _a):
        _f.stack.append(_f.code_obj.resolve_const(_a))

    def _h_ld_g(_f, _a):
        _n = _f.code_obj.names[_a]
        # PERF G2: compiler-certified globals skip the O(depth) frames-walk
        if _a not in _f.code_obj.global_only:
            if {v['active_frames']}:
                for _pf in reversed({v['active_frames']}[:-1]):
                    if _n in _pf.locals and _pf.locals[_n] is not {v['no_arg_sig']}:
                        _f.stack.append(_pf.locals[_n])
                        return
            if _f.captured_env and _n in _f.captured_env:
                _f.stack.append(_f.captured_env[_n])
                return
        if _n in _f.global_env:
            _f.stack.append(_f.global_env[_n])
        elif hasattr(__builtins__, _n):
            _f.stack.append(getattr(__builtins__, _n))
        elif isinstance(__builtins__, dict) and _n in __builtins__:
            _f.stack.append(__builtins__[_n])
        else:
            raise NameError(f"name '{{_n}}' is not defined")

    def _h_st_g(_f, _a):
        _f.global_env[_f.code_obj.names[_a]] = _f.stack.pop()

    def _h_ld_f(_f, _a):
        _f.stack.append(_f.locals.get(_f.code_obj.local_names[_a], None))

    def _h_st_f(_f, _a):
        _f.locals[_f.code_obj.local_names[_a]] = _f.stack.pop()

    def _h_dup(_f, _a):
        _f.stack.append(_f.stack[-1])

    def _h_pop(_f, _a):
        if _f.stack: _f.stack.pop()

    def _h_rot2(_f, _a):
        _top = _f.stack.pop(); _sec = _f.stack.pop()
        _f.stack.append(_top); _f.stack.append(_sec)

    def _h_rot3(_f, _a):
        _top = _f.stack.pop(); _sec = _f.stack.pop(); _thd = _f.stack.pop()
        _f.stack.append(_top); _f.stack.append(_thd); _f.stack.append(_sec)

    def _h_add(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val + _b)

    def _h_sub(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val - _b)

    def _h_mul(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val * _b)

    def _h_div(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val / _b)

    def _h_fdiv(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val // _b)

    def _h_mod(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val % _b)

    def _h_pow(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val ** _b)

    def _h_and(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val & _b)

    def _h_or(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val | _b)

    def _h_xor(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val ^ _b)

    def _h_lsh(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val << _b)

    def _h_rsh(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val >> _b)

    def _h_neg(_f, _a):
        _f.stack.append(-_f.stack.pop())

    def _h_not(_f, _a):
        _f.stack.append(not _f.stack.pop())

    def _h_inv(_f, _a):
        _f.stack.append(~_f.stack.pop())

    def _h_matmul(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val @ _b)

    def _h_cmp(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop()
        if _a == 0: _f.stack.append(_a_val < _b)
        elif _a == 1: _f.stack.append(_a_val <= _b)
        elif _a == 2: _f.stack.append(_a_val == _b)
        elif _a == 3: _f.stack.append(_a_val != _b)
        elif _a == 4: _f.stack.append(_a_val > _b)
        elif _a == 5: _f.stack.append(_a_val >= _b)
        elif _a == 6: _f.stack.append(_a_val in _b)
        elif _a == 7: _f.stack.append(_a_val not in _b)
        elif _a == 8: _f.stack.append(_a_val is _b)
        elif _a == 9: _f.stack.append(_a_val is not _b)
        else: _f.stack.append(False)

    def _h_chk_exc(_f, _a):
        _exc_type = _f.stack.pop()
        _exc_val = _f.stack.pop()
        if isinstance(_exc_val, type):
            _f.stack.append(issubclass(_exc_val, _exc_type))
        else:
            _f.stack.append(isinstance(_exc_val, _exc_type))

    def _h_jmp(_f, _a):
        _f.pc = _a * 3

    def _h_jmp_t(_f, _a):
        if _f.stack.pop(): _f.pc = _a * 3

    def _h_jmp_f(_f, _a):
        if not _f.stack.pop(): _f.pc = _a * 3

    def _h_jmp_f_p(_f, _a):
        if not _f.stack[-1]: _f.pc = _a * 3
        else: _f.stack.pop()

    def _h_jmp_t_p(_f, _a):
        if _f.stack[-1]: _f.pc = _a * 3
        else: _f.stack.pop()

    def _h_ret(_f, _a):
        return ({v['ret_sig']}, _f.stack.pop() if _f.stack else None)

    def _h_g_attr(_f, _a):
        _f.stack.append(getattr(_f.stack.pop(), _f.code_obj.names[_a]))

    def _h_s_attr(_f, _a):
        _obj = _f.stack.pop(); _val = _f.stack.pop()
        setattr(_obj, _f.code_obj.names[_a], _val)

    def _h_d_attr(_f, _a):
        delattr(_f.stack.pop(), _f.code_obj.names[_a])

    def _h_g_item(_f, _a):
        _k = _f.stack.pop(); _c = _f.stack.pop()
        _f.stack.append(_c[_k])

    def _h_s_item(_f, _a):
        _k = _f.stack.pop(); _c = _f.stack.pop(); _v = _f.stack.pop()
        _c[_k] = _v

    def _h_d_item(_f, _a):
        _k = _f.stack.pop(); _c = _f.stack.pop(); del _c[_k]

    def _h_d_fast(_f, _a):
        _k = _f.code_obj.local_names[_a]
        if _k in _f.locals: del _f.locals[_k]

    def _h_d_glob(_f, _a):
        _k = _f.code_obj.names[_a]
        if _k in _f.global_env: del _f.global_env[_k]

    def _h_b_list(_f, _a):
        _elts = [_f.stack.pop() for _ in range(_a)][::-1] if _a else []
        _f.stack.append(_elts)

    def _h_b_tup(_f, _a):
        _elts = [_f.stack.pop() for _ in range(_a)][::-1] if _a else []
        _f.stack.append(tuple(_elts))

    def _h_b_set(_f, _a):
        _elts = [_f.stack.pop() for _ in range(_a)][::-1] if _a else []
        _f.stack.append(set(_elts))

    def _h_b_dict(_f, _a):
        _d = {{}}
        _items = []
        for _ in range(_a):
            _dv = _f.stack.pop(); _dk = _f.stack.pop()
            _items.append((_dk, _dv))
        for _dk, _dv in reversed(_items):
            _d[_dk] = _dv
        _f.stack.append(_d)

    def _h_unp_seq(_f, _a):
        _seq = list(_f.stack.pop())
        for _item in reversed(_seq):
            _f.stack.append(_item)

    def _h_unp_ex(_f, _a):
        _before = _a & 0xFF
        _after = (_a >> 8) & 0xFF
        _seq = list(_f.stack.pop())
        _total = _sys_len(_seq)
        for _item in reversed(_seq[_total - _after:] if _after else []):
            _f.stack.append(_item)
        _f.stack.append(_seq[_before : _total - _after])
        for _item in reversed(_seq[:_before]):
            _f.stack.append(_item)

    def _h_b_slice(_f, _a):
        _step = _f.stack.pop(); _upper = _f.stack.pop(); _lower = _f.stack.pop()
        _f.stack.append(slice(_lower, _upper, _step))

    def _h_ld_drf(_f, _a):
        _n = _f.code_obj.names[_a]
        if {v['active_frames']}:
            for _pf in reversed({v['active_frames']}[:-1]):
                # sentinel-transparent: unfilled slots read as absent (matches
                # _h_ld_g and the slim-binder lazy locals)
                if _n in _pf.locals and _pf.locals[_n] is not {v['no_arg_sig']}:
                    _f.stack.append(_pf.locals[_n])
                    return
        # FIX (closure GAP-19/20 completion): a closure invoked AFTER its
        # enclosing frame has returned must still see the captured cell vars -
        # mirror the captured_env fallback used by _h_ld_g above.
        if _f.captured_env and _n in _f.captured_env:
            _f.stack.append(_f.captured_env[_n])
            return
        if _n in _f.global_env:
            _f.stack.append(_f.global_env[_n])
        elif hasattr(__builtins__, _n):
            _f.stack.append(getattr(__builtins__, _n))
        elif isinstance(__builtins__, dict) and _n in __builtins__:
            _f.stack.append(__builtins__[_n])
        else:
            raise NameError(f"free variable '{{_n}}' referenced before assignment in enclosing scope")

    def _h_st_drf(_f, _a):
        _n = _f.code_obj.names[_a]
        _val = _f.stack.pop()
        _updated = False
        if {v['active_frames']}:
            for _pf in reversed({v['active_frames']}[:-1]):
                if _n in _pf.locals:
                    _pf.locals[_n] = _val
                    _updated = True
                    break
        if _f.captured_env and _n in _f.captured_env:
            _f.captured_env[_n] = _val
            _updated = True
        if not _updated:
            _f.global_env[_n] = _val

    def _h_mk_fn(_f, _a):
        _fn_code_obj = _f.stack.pop()
        if isinstance(_fn_code_obj, tuple) and len(_fn_code_obj) == 3 and _fn_code_obj[0] == {repr(tok['lazy'])}:
            _fn_code_obj = {v['lazy_decode_fn']}(_fn_code_obj, _f.code_obj._k_enc)
        _dmap = None
        if bool(_a & 8):
            # (names_tuple, values_tuple) was pushed beneath the code const.
            # Kept per-closure: sharing a map on the shared code object would
            # give every instance the LAST evaluated defaults.
            _pair = _f.stack.pop()
            _names, _vals = _pair
            _dmap = dict(zip(_names, _vals))
        _is_async = bool(_a & 1)
        _is_gen = bool(_a & 2)
        # FIX (closure cell semantics): closures previously snapshotted a COPY
        # of the defining frame's locals, so sibling closures never saw each
        # other's nonlocal writes after the enclosing frame returned (native
        # Python shares live cells). The chain delegates reads/writes to the
        # ORIGIN frames' live locals dicts - no copies, any nesting depth.
        _captured_env = {v['env_chain_cls']}(_f.locals, _f.captured_env)
        if _is_gen and _is_async:
            def _make_agen(_fco, _cenv, _dfl):
                def _agfactory(*_args, **_kwargs):
                    _d_cls = getattr(_agfactory, '_vm_def_cls', getattr(_fco, 'defining_class', None))
                    return {v['agen_cls']}(_fco, _args, _kwargs, _cenv, _d_cls, _dfl)
                _agfactory._fco = _fco
                _agfactory.__name__ = _fco.name
                return _agfactory
            _f.stack.append(_make_agen(_fn_code_obj, _captured_env, _dmap))
        elif _is_gen:
            def _make_gen(_fco, _cenv, _dfl):
                def _gfactory(*_args, **_kwargs):
                    _d_cls = getattr(_gfactory, '_vm_def_cls', getattr(_fco, 'defining_class', None))
                    return {v['gen_cls']}(_fco, _args, _kwargs, _cenv, _d_cls, _dfl)
                _gfactory._fco = _fco
                _gfactory.__name__ = _fco.name
                return _gfactory
            _f.stack.append(_make_gen(_fn_code_obj, _captured_env, _dmap))
        elif _is_async:
            def _make_wrapped_async(_fco, _cenv, _dfl):
                async def _wrapped_async(*_args, **_kwargs):
                    _d_cls = getattr(_wrapped_async, '_vm_def_cls', getattr(_fco, 'defining_class', None))
                    return await {v['call_vm_async_fn']}(_fco, _args, _kwargs, _cenv, _def_cls=_d_cls, _defaults=_dfl)
                _wrapped_async._fco = _fco
                _wrapped_async.__name__ = _fco.name
                return _wrapped_async
            _f.stack.append(_make_wrapped_async(_fn_code_obj, _captured_env, _dmap))
        else:
            def _make_wrapped(_fco, _cenv, _dfl):
                def _wrapped(*_args, **_kwargs):
                    _d_cls = getattr(_wrapped, '_vm_def_cls', getattr(_fco, 'defining_class', None))
                    return {v['call_vm_fn']}(_fco, _args, _kwargs, _cenv, _def_cls=_d_cls, _defaults=_dfl)
                _wrapped._fco = _fco
                _wrapped.__name__ = _fco.name
                return _wrapped
            _f.stack.append(_make_wrapped(_fn_code_obj, _captured_env, _dmap))

    def _h_call_fn(_f, _a):
        _args = [_f.stack.pop() for _ in range(_a)][::-1] if _a else []
        _fn = _f.stack.pop()
        _f.stack.append(_fn(*_args))

    def _wrap_anext_coro(_coro):
        async def _runner():
            try:
                return (True, await _coro)
            except StopAsyncIteration:
                return (False, None)
        return _runner()

    def _h_call_fn_async(_f, _a):
        _args = [_f.stack.pop() for _ in range(_a)][::-1] if _a else []
        _fn = _f.stack.pop()
        # Identity-only await detection. The old name-table heuristic
        # legacy detection misfired on any global whose name index
        # collided with the await slot, hijacking plain calls like worker([7,8]).
        in_async = {v['async_depth']}[0] > 0
        {_DBG_CALLA}
        if _fn is _g_env.get({repr(tok['await_fn'])}):
            import inspect
            if _args and (inspect.iscoroutine(_args[0]) or inspect.isawaitable(_args[0])):
                if in_async:
                    # Native hand-off onto the running loop (no nested pools).
                    return ({v['await_sig']}, _args[0])
                _f.stack.append({v['vm_await_fn']}(_args[0]))
            else:
                _f.stack.append(_args[0] if _args else None)
        elif _fn is _g_env.get({repr(tok['anext_fn'])}):
            if in_async and _args:
                try:
                    _coro = _args[0].__anext__()
                except StopAsyncIteration:
                    _f.stack.append((False, None))
                    return
                return ({v['await_sig']}, _wrap_anext_coro(_coro))
            _f.stack.append({v['vm_anext_fn']}(*_args))
        elif hasattr(_fn, '__name__') and _fn.__name__ == '_vm_await':
            import inspect
            if _args and (inspect.iscoroutine(_args[0]) or inspect.isawaitable(_args[0])):
                return ({v['await_sig']}, _args[0])
            else:
                _f.stack.append(_args[0] if _args else None)
        else:
            _f.stack.append(_fn(*_args))

    def _h_call_kw(_f, _a):
        _n_args = _a & 0xFF
        _n_kw = (_a >> 8) & 0xFF
        _kw = {{}}
        for _ in range(_n_kw):
            _v = _f.stack.pop(); _k = _f.stack.pop(); _kw[_k] = _v
        _args = [_f.stack.pop() for _ in range(_n_args)][::-1] if _n_args else []
        _fn = _f.stack.pop()
        _f.stack.append(_fn(*_args, **_kw))

    def _h_call_ex(_f, _a):
        _kw = _f.stack.pop() if (_a & 1) else {{}}
        _star_args = list(_f.stack.pop())
        _fn = _f.stack.pop()
        _f.stack.append(_fn(*_star_args, **_kw))

    def _h_b_cls(_f, _a):
        _cls_code = _f.stack.pop()
        if isinstance(_cls_code, tuple) and _sys_len(_cls_code) == 3 and _cls_code[0] == {repr(tok['lazy'])}:
            _cls_code = {v['lazy_decode_fn']}(_cls_code, _f.code_obj._k_enc)
        _meta_param = _f.stack.pop()
        _bases = _f.stack.pop()
        _cname = _f.stack.pop()
        _cls_loc = {{}}
        _cls_frame = {v['attach_isa_fn']}({v['frame_cls']}(_cls_code, _cls_loc, _g_env))
        {v['eval_frame_fn']}(_cls_frame)
        _meta = _meta_param
        if _meta is None and hasattr(_bases, '__iter__'):
            for _b in _bases:
                if isinstance(_b, type) and _b is not object and issubclass(_b, type):
                    _meta = _b
                    break
        if _meta is None:
            _meta = type
        _new_class = _meta(_cname, tuple(_bases), _cls_loc)
        for _c in getattr(_cls_code, 'constants', []):
            if hasattr(_c, 'defining_class'):
                _c.defining_class = _new_class
        for _k, _v in _cls_loc.items():
            if callable(_v):
                try:
                    setattr(_v, '__class__', _new_class)
                    setattr(_v, '_vm_def_cls', _new_class)
                    if hasattr(_v, '_fco'):
                        setattr(_v._fco, 'defining_class', _new_class)
                except Exception:
                    pass
        _f.stack.append(_new_class)

    def _h_imp_n(_f, _a):
        _n = _f.code_obj.names[_a]
        if _n.startswith({repr(tok['fl_prefix'])}):
            # fromlist sentinel emitted by visit_ImportFrom:
            # sentinel-prefix lookup + csv(names) -> return SUBMODULE.
            _rest = _n[len({repr(tok['fl_prefix'])}):]
            _mod, _, _csv = _rest.partition(chr(0))
            _f.stack.append(__import__(_mod, fromlist=tuple(_csv.split(','))))
        else:
            _f.stack.append(__import__(_n))

    def _h_imp_f(_f, _a):
        _m = _f.stack[-1]
        _f.stack.append(getattr(_m, _f.code_obj.names[_a]))

    def _h_g_iter(_f, _a):
        _f.stack.append(iter(_f.stack.pop()))

    def _h_for_it(_f, _a):
        _it = _f.stack.pop()
        try:
            _next_val = next(_it)
            _f.stack.append(_next_val)
        except StopIteration:
            _f.pc = _a * 3

    def _h_st_fin(_f, _a):
        _f.exc_handlers.append(_a * 3)

    def _h_pop_blk(_f, _a):
        if _f.exc_handlers: _f.exc_handlers.pop()

    def _h_raise(_f, _a):
        if _a >= 2:
            # raise EXC from CAUSE  (arg bit 2 = cause present)
            _cause = _f.stack.pop() if _f.stack else None
            _exc = _f.stack.pop() if _f.stack else None
            if _exc is None:
                _exc = _f.current_exception or RuntimeError("Exception raised")
            if _cause is not None:
                try:
                    _exc.__cause__ = _cause
                    _exc.__suppress_context__ = True
                except Exception:
                    pass
            raise _exc
        _exc = _f.stack.pop() if _f.stack else None
        if _exc is None:
            _exc = _f.current_exception or RuntimeError("Exception raised")
        raise _exc

    def _h_nop(_f, _a):
        pass

    def _h_yield(_f, _a):
        _v = _f.stack.pop()
        return ({v['yield_sig']}, _v)

    def _h_yield_from(_f, _a):
        if _f.dele is None:
            # First entry: stack top is the sub-iterable/generator
            _sub = _f.stack.pop()
            _f.last_sent = None
            if hasattr(_sub, 'send'):
                _f.dele = _sub
            else:
                _f.dele = iter(_sub)
        else:
            # Resumed: wrapper pushed the value sent() into this generator;
            # forward it into the delegated generator.
            _f.last_sent = _f.stack.pop()
        try:
            if hasattr(_f.dele, 'send'):
                _item = _f.dele.send(_f.last_sent)
            else:
                _item = next(_f.dele)
            # Rewind PC so the resume re-enters THIS instruction (it drives the
            # whole delegation loop across suspensions).
            _f.pc -= 3
            return ({v['yield_sig']}, _item)
        except StopIteration as _e:
            _f.dele = None
            _f.stack.append(getattr(_e, 'value', None))
        except BaseException:
            if _f.dele is not None and hasattr(_f.dele, 'close'):
                try:
                    _f.dele.close()
                except Exception:
                    pass
            _d = _f.dele
            _f.dele = None
            raise

    def _h_halt(_f, _a):
        return {v['halt_sig']}

    {v['dispatch_tbl']} = [{v['trap_fn']}] * 256
    {v['dispatch_tbl_async']} = [{v['trap_fn']}] * 256
    {reg_stmts}
    {v['dispatch_tbl_async']}[{slot_call_fn}] = _h_call_fn_async

    # Level >= 4: per-function affine ISA keys derived from master seed + code
    # object name. Levels < 4 share the single build-wide (M, A) pair.

    def {v['bind_frame_fn']}(_fn_code, _passed_args, _passed_kwargs=None, _captured_env=None, _def_cls=None, _defaults=None):
        # PERF G1 note: an earlier "slim binder" (prefill params only) measured
        # SLOWER on call-heavy workloads than this single C-level dict
        # comprehension over local_names - kept the comprehension.
        _loc = {{_aname: {v['no_arg_sig']} for _aname in _fn_code.local_names}}
        _rem_kwargs = dict(_passed_kwargs or {{}})
        _pos_count = _sys_len(_fn_code.arg_names)
        for _idx, _aname in enumerate(_fn_code.arg_names):
            if _idx < _sys_len(_passed_args):
                _loc[_aname] = _passed_args[_idx]
            elif _aname in _rem_kwargs:
                _loc[_aname] = _rem_kwargs.pop(_aname)
        if _fn_code.vararg_name:
            _loc[_fn_code.vararg_name] = tuple(_passed_args[_pos_count:])
        elif _sys_len(_passed_args) > _pos_count and not _fn_code.name.startswith('<'):
            # FIX (GAP-26): CPython raises on surplus positionals without *args;
            # the old binder silently discarded them. Synthetic comps exempt.
            raise TypeError(f"{{_fn_code.name}}() takes {{_pos_count}} positional arguments but {{_sys_len(_passed_args)}} were given")
        for _kname in getattr(_fn_code, 'kwonly_names', []):
            if _kname in _rem_kwargs:
                _loc[_kname] = _rem_kwargs.pop(_kname)
        if _fn_code.kwarg_name:
            _loc[_fn_code.kwarg_name] = _rem_kwargs
        elif _rem_kwargs and not _fn_code.name.startswith('<'):
            # FIX (GAP-26b): keyword-typo masking - reject unknown kwargs.
            # Synthetic functions (comprehensions <listcomp> etc.) are exempt:
            # their compiler emits synthetic params bound by the comp loop.
            raise TypeError(f"{{_fn_code.name}}() got an unexpected keyword argument '{{next(iter(_rem_kwargs))}}'")
        _f = {v['frame_cls']}(_fn_code, _loc, _g_env)
        _f.captured_env = _captured_env or {{}}
        _f.defining_class = _def_cls
        if _defaults:
            for _dn, _dv in _defaults.items():
                if _loc.get(_dn) is {v['no_arg_sig']}:
                    _loc[_dn] = _dv
        for _an in list(_fn_code.arg_names) + list(getattr(_fn_code, 'kwonly_names', [])):
            if _loc.get(_an) is {v['no_arg_sig']} and not _fn_code.name.startswith('<') and _an not in getattr(_fn_code, 'kwonly_default_names', ()):
                # FIX (GAP-27): native-shaped missing-argument error instead of
                # leaking the internal sentinel into user code. Runs AFTER
                # default application; ONLY real parameters checked. Kwonly
                # params WITH defaults are exempt: their default is applied by
                # the function-body preamble at call time (late-bound channel).
                raise TypeError(f"{{_fn_code.name}}() missing required argument '{{_an}}'")
        {v['attach_isa_fn']}(_f)
        return _f

    def {v['call_vm_fn']}(_fn_code, _passed_args, _passed_kwargs=None, _captured_env=None, _def_cls=None, _defaults=None):
        _f = {v['bind_frame_fn']}(_fn_code, _passed_args, _passed_kwargs, _captured_env, _def_cls, _defaults)
        {v['active_frames']}.append(_f)
        try:
            return {v['eval_frame_fn']}(_f)
        finally:
            if {v['active_frames']}: {v['active_frames']}.pop()

    _orig_super = __builtins__.super if hasattr(__builtins__, 'super') else __builtins__['super']

    class {v['gen_cls']}:
        def __init__(self, _fco, _args, _kwargs, _cenv, _dcls, _dfl=None):
            self._fco = _fco
            self._args = _args
            self._kwargs = _kwargs
            self._cenv = _cenv
            self._dcls = _dcls
            self._dfl = _dfl
            self._fr = None
            self._done = False
        def __iter__(self):
            return self
        def __next__(self):
            return self.send(None)
        def _start(self):
            self._fr = {v['bind_frame_fn']}(self._fco, self._args, self._kwargs, self._cenv, self._dcls, self._dfl)
            self._fr.is_generator = True
            {v['active_frames']}.append(self._fr)
        def send(self, _v):
            if self._done:
                raise StopIteration
            if self._fr is None:
                if _v is not None:
                    raise TypeError("can't send non-None value to a just-started generator")
                self._start()
            else:
                self._fr.stack.append(_v)
            try:
                _r = {v['eval_frame_fn']}(self._fr)
            except BaseException:
                self._done = True
                if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
                raise
            if isinstance(_r, tuple) and _sys_len(_r) == 2 and _r[0] is {v['yield_sig']}:
                return _r[1]
            self._done = True
            if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
            raise StopIteration(_r)
        def throw(self, _e, _val=None):
            if self._done or self._fr is None:
                if self._done:
                    raise _e
                self._start()
            self._fr.injected_exc = _e
            try:
                return self.send(None)
            except StopIteration:
                raise StopIteration from None
        def close(self):
            if self._done:
                return
            if self._fr is None:
                self._done = True
                return
            self._fr.injected_exc = GeneratorExit()
            try:
                _r = {v['eval_frame_fn']}(self._fr)
            except (GeneratorExit, StopIteration):
                self._done = True
                if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
                return
            except BaseException:
                self._done = True
                if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
                raise
            self._done = True
            if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
            if isinstance(_r, tuple) and _sys_len(_r) == 2 and _r[0] is {v['yield_sig']}:
                raise RuntimeError("generator ignored GeneratorExit")

    class {v['agen_cls']}:
        def __init__(self, _fco, _args, _kwargs, _cenv, _dcls, _dfl=None):
            self._fco = _fco
            self._args = _args
            self._kwargs = _kwargs
            self._cenv = _cenv
            self._dcls = _dcls
            self._dfl = _dfl
            self._fr = None
            self._done = False
        def __aiter__(self):
            return self
        def _start(self):
            self._fr = {v['bind_frame_fn']}(self._fco, self._args, self._kwargs, self._cenv, self._dcls, self._dfl)
            self._fr.is_generator = True
            {v['active_frames']}.append(self._fr)
        async def __anext__(self):
            if self._done:
                raise StopAsyncIteration
            if self._fr is None:
                self._start()
            try:
                _r = await {v['eval_frame_async_fn']}(self._fr)
            except (StopAsyncIteration, StopIteration):
                self._done = True
                if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
                raise StopAsyncIteration
            except BaseException:
                self._done = True
                if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
                raise
            if isinstance(_r, tuple) and _sys_len(_r) == 2 and _r[0] is {v['yield_sig']}:
                return _r[1]
            self._done = True
            if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
            raise StopAsyncIteration
        async def asend(self, _v):
            if self._done:
                raise StopAsyncIteration
            if self._fr is None:
                self._start()
            else:
                self._fr.stack.append(_v)
            try:
                _r = await {v['eval_frame_async_fn']}(self._fr)
            except BaseException:
                self._done = True
                if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
                raise
            if isinstance(_r, tuple) and _sys_len(_r) == 2 and _r[0] is {v['yield_sig']}:
                return _r[1]
            self._done = True
            if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
            raise StopAsyncIteration
        async def aclose(self):
            if self._done or self._fr is None:
                self._done = True
                return
            self._fr.injected_exc = GeneratorExit()
            try:
                await {v['eval_frame_async_fn']}(self._fr)
            except BaseException:
                pass
            self._done = True
            if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)

    def __vm_ayieldfrom___helper(_sub):
        async def _agen_delegate():
            if hasattr(_sub, '__aiter__'):
                async for _x in _sub:
                    yield _x
            else:
                for _x in iter(_sub):
                    yield _x
        return _agen_delegate()

    _g_env['__vm_ayieldfrom__'] = __vm_ayieldfrom___helper

    def {v['vm_super_fn']}(*_sargs):
        if _sys_len(_sargs) == 0 and {v['active_frames']}:
            _cur = {v['active_frames']}[-1]
            _self_obj = None
            for _k in _cur.code_obj.arg_names:
                _val = _cur.locals.get(_k)
                if _val is not None and _val is not {v['no_arg_sig']}:
                    _self_obj = _val
                    break
            if _self_obj is not None:
                _def_cls = getattr(_cur, 'defining_class', None)
                if _def_cls is None and hasattr(_cur.code_obj, 'defining_class'):
                    _def_cls = _cur.code_obj.defining_class
                if _def_cls is not None:
                    return _orig_super(_def_cls, _self_obj)
                if isinstance(_self_obj, type):
                    return _orig_super(_self_obj, _self_obj)
                return _orig_super(type(_self_obj), _self_obj)
        return _orig_super(*_sargs)

    _g_env['super'] = {v['vm_super_fn']}

    def {v['vm_await_fn']}(_val):
        import inspect, asyncio
        if inspect.iscoroutine(_val) or inspect.isawaitable(_val):
            try:
                _loop = asyncio.get_event_loop()
                if _loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _pool:
                        return _pool.submit(asyncio.run, _val).result()
                return _loop.run_until_complete(_val)
            except Exception:
                return asyncio.run(_val)
        return _val

    _g_env[{repr(tok['await_fn'])}] = {v['vm_await_fn']}

    def {v['vm_anext_fn']}(_aiter):
        import inspect, asyncio
        try:
            _coro = _aiter.__anext__()
        except StopAsyncIteration:
            return (False, None)
        if inspect.iscoroutine(_coro) or inspect.isawaitable(_coro):
            try:
                _loop = asyncio.get_event_loop()
                if _loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _pool:
                        return (True, _pool.submit(asyncio.run, _coro).result())
                return (True, _loop.run_until_complete(_coro))
            except StopAsyncIteration:
                return (False, None)
        return (True, _coro)

    _g_env[{repr(tok['anext_fn'])}] = {v['vm_anext_fn']}
    _g_env[{repr(tok['match_rest'])}] = (lambda _subj, _excl: {{k: v for k, v in _subj.items() if k not in _excl}})
    # Match-case protocol helpers (TVM 4.0 GAP-33/35):
    def __tvm_is_seq__(_o):
        if isinstance(_o, (str, bytes, bytearray)):
            return False
        # Exclude mappings (dict has __len__/__getitem__ but is NOT a sequence
        # under PEP 634) - mirrors collections.abc.Sequence semantics closely.
        if hasattr(_o, 'keys'):
            return False
        return hasattr(_o, '__len__') and hasattr(_o, '__getitem__')
    def __tvm_is_map__(_o):
        return hasattr(_o, 'keys') and hasattr(_o, '__getitem__')
    def __tvm_margs__(_subj, _cls, _idx):
        try:
            _ma = getattr(_cls, '__match_args__', None)
        except Exception:
            return {v['no_arg_sig']}
        if _ma is None or _idx >= _sys_len(tuple(_ma)):
            return {v['no_arg_sig']}
        return getattr(_subj, tuple(_ma)[_idx], {v['no_arg_sig']})
    _g_env['__tvm_is_seq'] = __tvm_is_seq__
    _g_env['__tvm_is_map'] = __tvm_is_map__
    _g_env['__tvm_margs'] = __tvm_margs__

    def __tvm_snap__(_names):
        # Captures may be frame LOCALS (function scope) or module globals;
        # resolve against the innermost active frame first.
        _sent = _g_env.get({repr(tok['no_arg'])})
        _src = {v['active_frames']}[-1].locals if {v['active_frames']} else _g_env
        return {{_n: _src.get(_n, _sent) for _n in _names}}
    def __tvm_restore__(_names, _snap):
        _tgt = {v['active_frames']}[-1].locals if {v['active_frames']} else _g_env
        for _n in _names:
            _v = _snap.get(_n)
            if _v is _g_env.get({repr(tok['no_arg'])}):
                _tgt.pop(_n, None)
            else:
                _tgt[_n] = _v
    _g_env['__tvm_snap'] = __tvm_snap__
    _g_env['__tvm_restore'] = __tvm_restore__

    def {tok['bind_defaults']}(_co, _pair):
        return _co

    _g_env[{repr(tok['bind_defaults'])}] = {tok['bind_defaults']}

    # Level-4 per-function ISA divergence infrastructure lives below; the
    # enable flag is interpolated from the emitter scope.
    _isa_fwd_cache = {{}}
    # PERF G1: one shared slot table per permutation object (M/A are constant
    # for the whole build, so the table only depends on _perm identity).
    _slot_cache = {{}}
    def {v['attach_isa_fn']}(_fr):
        if {int(vm_level >= 4)} and {int(_TVM_L4_PERM_ENABLED)}:
            _n = _fr.code_obj.name
            _p = _isa_fwd_cache.get(_n)
            if _p is None:
                _p = {v['perm_rt_fn']}(_n, _master_seed)
                _isa_fwd_cache[_n] = _p
            _fr._perm = _p
        else:
            _fr._perm = None
        # PERF G1: precompute the affine dispatch slot per opcode ONCE per
        # permutation - hoisted out of the hot loop. Same formula as before,
        # ISA randomization is unchanged.
        _pk = id(_fr._perm)
        _slot = _slot_cache.get(_pk)
        if _slot is None:
            _slot = [0] * 256
            _pp = _fr._perm
            for _o in range(256):
                _slot[_o] = (((_pp[_o]) if _pp is not None else _o) * {M} + {A}) & 0xFF
            _slot_cache[_pk] = _slot
        _fr._slot = _slot
        return _fr

    async def {v['eval_frame_async_fn']}(_frame):
        _c_arr = _frame.code_obj.code
        _c_len = _sys_len(_c_arr)
        {v['async_depth']}[0] += 1
        {_DBG_AE}
        try:
            while _frame.pc < _c_len:
                try:
                    if _frame.injected_exc is not None:
                        _inj = _frame.injected_exc
                        _frame.injected_exc = None
                        raise _inj
                    _op = _c_arr[_frame.pc]
                    _arg = (_c_arr[_frame.pc+1] << 8) | _c_arr[_frame.pc+2]
                    _frame.pc += 3

                    # PERF G1: precomputed slot + type() is tuple (see sync loop)
                    _h = {v['dispatch_tbl_async']}[_frame._slot[_op]]
                    _sig = _h(_frame, _arg)
                    if _sig is not None:
                        if _sig is {v['halt_sig']}:
                            break
                        if type(_sig) is tuple and _sys_len(_sig) == 2:
                            if _sig[0] is {v['ret_sig']}:
                                return _sig[1]
                            elif _sig[0] is {v['await_sig']}:
                                _res = await _sig[1]
                                _frame.stack.append(_res)
                            elif _sig[0] is {v['yield_sig']}:
                                return _sig
                except BaseException as _e:
                    _frame.current_exception = _e
                    if _frame.exc_handlers:
                        _handler_pc = _frame.exc_handlers.pop()
                        _frame.pc = _handler_pc
                        _frame.stack.append(_e)
                    else:
                        raise _e
            return _frame.stack.pop() if _frame.stack else None
        finally:
            {v['async_depth']}[0] -= 1
            if {int(vm_level >= 3)} and not _frame.is_generator:
                _frame.stack.clear()
                _frame.exc_handlers.clear()
                _frame.current_exception = None

    async def {v['call_vm_async_fn']}(_fn_code, _passed_args, _passed_kwargs=None, _captured_env=None, _def_cls=None, _defaults=None):
        _f = {v['bind_frame_fn']}(_fn_code, _passed_args, _passed_kwargs, _captured_env, _def_cls, _defaults)
        {v['active_frames']}.append(_f)
        try:
            return await {v['eval_frame_async_fn']}(_f)
        finally:
            if {v['active_frames']}: {v['active_frames']}.pop()

    def {v['eval_frame_fn']}(_frame):
        _c_arr = _frame.code_obj.code
        _c_len = _sys_len(_c_arr)
        try:
            while _frame.pc < _c_len:
                try:
                    if _frame.injected_exc is not None:
                        _inj = _frame.injected_exc
                        _frame.injected_exc = None
                        raise _inj
                    _op = _c_arr[_frame.pc]
                    _arg = (_c_arr[_frame.pc+1] << 8) | _c_arr[_frame.pc+2]
                    _frame.pc += 3

                    # PERF G1: slot precomputed at frame attach; type() is tuple
                    # avoids the isinstance virtual-call overhead in this loop.
                    _h = {v['dispatch_tbl']}[_frame._slot[_op]]
                    _sig = _h(_frame, _arg)
                    if _sig is not None:
                        if _sig is {v['halt_sig']}:
                            break
                        if type(_sig) is tuple and _sys_len(_sig) == 2 and _sig[0] is {v['ret_sig']}:
                            return _sig[1]
                        if type(_sig) is tuple and _sys_len(_sig) == 2 and _sig[0] is {v['yield_sig']}:
                            return _sig
                except BaseException as _e:
                    _frame.current_exception = _e
                    if _frame.exc_handlers:
                        _handler_pc = _frame.exc_handlers.pop()
                        _frame.pc = _handler_pc
                        _frame.stack.append(_e)
                    else:
                        raise _e
            return _frame.stack.pop() if _frame.stack else None
        finally:
            if {int(vm_level >= 3)} and not _frame.is_generator:
                _frame.stack.clear()
                _frame.exc_handlers.clear()
                _frame.current_exception = None

    _initial_frame = {v['attach_isa_fn']}({v['frame_cls']}(_root_code, {{}}, _g_env))
    {v['eval_frame_fn']}(_initial_frame)

{v['interp_fn']}({repr(serialized_root_packet)}, {repr(master_seed)}, {repr(runtime_salt)})
"""
    return src.strip()


def _vm_obfuscate(code_str: str, seed=None, vm_level: int = 1) -> str:
    """
    Tr0ngX True Virtual Machine (TVM 2.0) Obfuscation Engine.
    100% Zero-exec full virtualization. Directly compiles Python AST into Custom ISA Bytecode
    and executes via a Polymorphic Frame-Based Virtual Machine Interpreter with dynamic AEAD stream encryption.
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError:
        return code_str

    build_seed = seed if seed is not None else secrets.randbits(64)
    rng = random.Random(build_seed)

    # 1. Generate per-build Polymorphic ISA Mapping (0..255)
    all_opcodes = list(range(1, 255))
    rng.shuffle(all_opcodes)
    isa_map = {}
    standard_opcodes = [
        _TVMOpcodes.LOAD_CONST, _TVMOpcodes.LOAD_GLOBAL, _TVMOpcodes.STORE_GLOBAL,
        _TVMOpcodes.LOAD_FAST, _TVMOpcodes.STORE_FAST, _TVMOpcodes.DUP_TOP, _TVMOpcodes.POP_TOP,
        _TVMOpcodes.ROT_TWO, _TVMOpcodes.ROT_THREE,
        _TVMOpcodes.BINARY_ADD, _TVMOpcodes.BINARY_SUB, _TVMOpcodes.BINARY_MUL,
        _TVMOpcodes.BINARY_DIV, _TVMOpcodes.BINARY_FLOORDIV, _TVMOpcodes.BINARY_MOD,
        _TVMOpcodes.BINARY_POW, _TVMOpcodes.BINARY_AND, _TVMOpcodes.BINARY_OR,
        _TVMOpcodes.BINARY_XOR, _TVMOpcodes.BINARY_LSHIFT, _TVMOpcodes.BINARY_RSHIFT,
        _TVMOpcodes.UNARY_NEG, _TVMOpcodes.UNARY_NOT, _TVMOpcodes.UNARY_INVERT,
        _TVMOpcodes.BINARY_MATMUL,
        _TVMOpcodes.COMPARE_OP, _TVMOpcodes.JUMP, _TVMOpcodes.JUMP_IF_TRUE,
        _TVMOpcodes.JUMP_IF_FALSE, _TVMOpcodes.JUMP_IF_FALSE_OR_POP, _TVMOpcodes.JUMP_IF_TRUE_OR_POP,
        _TVMOpcodes.RETURN_VALUE, _TVMOpcodes.GET_ATTR, _TVMOpcodes.SET_ATTR,
        _TVMOpcodes.GET_ITEM, _TVMOpcodes.SET_ITEM, _TVMOpcodes.DEL_ITEM,
        _TVMOpcodes.DEL_ATTR, _TVMOpcodes.DEL_FAST, _TVMOpcodes.DEL_GLOBAL,
        _TVMOpcodes.BUILD_LIST, _TVMOpcodes.BUILD_TUPLE, _TVMOpcodes.BUILD_SET, _TVMOpcodes.BUILD_DICT,
        _TVMOpcodes.UNPACK_SEQUENCE, _TVMOpcodes.BUILD_SLICE, _TVMOpcodes.UNPACK_EX,
        _TVMOpcodes.MAKE_FUNCTION, _TVMOpcodes.CALL_FUNCTION, _TVMOpcodes.CALL_FUNCTION_KW,
        _TVMOpcodes.BUILD_CLASS, _TVMOpcodes.IMPORT_NAME, _TVMOpcodes.IMPORT_FROM,
        _TVMOpcodes.CALL_FUNCTION_EX, _TVMOpcodes.LOAD_DEREF, _TVMOpcodes.STORE_DEREF,
        _TVMOpcodes.GET_ITER, _TVMOpcodes.FOR_ITER, _TVMOpcodes.SETUP_FINALLY,
        _TVMOpcodes.POP_BLOCK, _TVMOpcodes.RAISE_VARARGS, _TVMOpcodes.CHECK_EXC_MATCH,
        _TVMOpcodes.HALT, _TVMOpcodes.NOP, _TVMOpcodes.TRAP,
        _TVMOpcodes.YIELD_VALUE, _TVMOpcodes.YIELD_FROM
    ]
    for idx, std_op in enumerate(standard_opcodes):
        isa_map[std_op] = all_opcodes[idx]

    # 2. Lower AST into Custom TVM Instructions with VM-level hardening
    _TVM_TOKENS.clear()
    _TVM_TOKENS.update({
        'lazy': '__' + rd()[:14],
        'no_arg': '_' + rd()[:12],
        'await_fn': '__' + rd()[:14],
        'anext_fn': '__' + rd()[:14],
        'match_rest': '__' + rd()[:14],
        'bind_defaults': '__' + rd()[:14],
        'fl_prefix': '__' + rd()[:14],
    })
    compiler = _TVMASTCompiler(name='<module>', is_function=False, vm_level=vm_level, rng=rng)
    compiler.vm_annotations = _cfg._EngineState.vm_annotations
    compiler._scan_scope(tree.body)
    if compiler.vm_annotations:
        compiler.emit(_TVMOpcodes.BUILD_MAP, 0)
        compiler.emit(_TVMOpcodes.STORE_GLOBAL,
                      compiler.code_obj.get_name_idx('__annotations__'))
    for stmt in tree.body:
        compiler.visit(stmt)
    root_code = compiler.finalize()

    # 3. Emit Polymorphic Runtime Interpreter 2.0 with AEAD & Dynamic Dispatch
    runtime = _vm_emit_runtime_interpreter_v2(root_code, isa_map, vm_level, rng,
                                              vm_debug=False)
    return runtime

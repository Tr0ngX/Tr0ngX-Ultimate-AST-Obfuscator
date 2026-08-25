# AUTO-SPLIT from tr0ngx_obfuscator.py (mechanical slice, imports repaired)
import builtins as _builtins_mod
import ast
import random
import copy

from . import config as _cfg
from .names import _trx_rand, _gen_cjk_name


# ═══════════════════════════════════════════════════════════════
# VELIMATIX ENGINE - ADVANCED AST TRANSFORMERS
# ═══════════════════════════════════════════════════════════════

class Utils:
    def randomize_name(alphabet: str, length: int) -> str:
        if _cfg._EngineState.use_cjk_names:
            return _gen_cjk_name(min_len=max(6, length // 2), max_len=max(8, length))
        name = ''.join(random.choice(alphabet) for _ in range(length))
        while name[0].isdigit():
            name = ''.join(random.choice(alphabet) for _ in range(length))
        return name

    def generate_next_num(current: int, max: int):
        next_val = current + random.randint(1, 1000)
        return next_val

    def find_parent(node, targets):
        parent = node.parent
        while True:
            for target in targets:
                if isinstance(parent, target):
                    return parent
                elif isinstance(parent, ast.Module):
                    return None
            parent = parent.parent

    def find_class(tree, node: ast.Call):
        for _node in ast.walk(tree):
            for child in ast.iter_child_nodes(_node):
                name = node.func.id
                if isinstance(child, ast.FunctionDef):
                    if child.name == name:
                        return child.parent
                elif isinstance(child, ast.ClassDef):
                    if child.name == name:
                        return child
        return None

    def get_chance():
        return random.randint(0, 100)


class BiOpaqueUtils:
    possible_args = []
    possible_functions = []
    alphabet = ""
    length = 16
    safe_mode = False

    def get_possible_functions(tree: ast.Module):
        if BiOpaqueUtils.possible_functions != []:
            return BiOpaqueUtils.possible_functions
        # SPLIT-FIX: resolve the real builtins MODULE explicitly. When the
        # engine runs inside an imported package, the module-level
        # `__builtins__` is a plain dict whose dir() leaks dict/object dunder
        # methods (__delitem__, __or__, __init_subclass__, ...) into generated
        # code as bare global names -> NameError in artifacts. The monolith
        # (executed as __main__) always saw the module here.
        possible_functions = [ast.Name(id=func_id) for func_id in dir(_builtins_mod) if not func_id.startswith("_")]
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.FunctionDef):
                    if isinstance(child.parent, ast.ClassDef):
                        possible_functions.append(ast.Attribute(value=ast.Name(id=child.parent.name), attr=child.name))
                    else:
                        possible_functions.append(ast.Name(id=child.name))
        BiOpaqueUtils.possible_functions = possible_functions
        return BiOpaqueUtils.possible_functions

    def get_possible_args(tree: ast.Module):
        if BiOpaqueUtils.possible_args != []:
            return BiOpaqueUtils.possible_args
        possible_args = []
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.Call):
                    for arg in child.args:
                        # ★ Skip Starred expressions — invalid outside call context
                        if not isinstance(arg, ast.Starred):
                            possible_args.append(arg)
        BiOpaqueUtils.possible_args = possible_args
        return BiOpaqueUtils.possible_args

    def get_random_function(tree: ast.Module):
        possible_functions = BiOpaqueUtils.get_possible_functions(tree)
        return random.choice(possible_functions)

    def get_random_args(tree: ast.Module):
        possible_args = BiOpaqueUtils.get_possible_args(tree)
        if not possible_args:
            return []
        return [random.choice(possible_args) for i in range(random.randint(0, 2))]

    def generate_bogus_body(tree, node):
        bogus = type(node).__new__(type(node))
        bogus.__dict__.update(node.__dict__)
        for name, field in ast.iter_fields(bogus):
            if isinstance(field, ast.Call):
                new_call = type(field).__new__(type(field))
                new_call.__dict__.update(field.__dict__)
                if isinstance(new_call.func, ast.Name) or isinstance(new_call.func, ast.Attribute):
                    new_call.func = BiOpaqueUtils.get_random_function(tree)
                    # ★ Filter starred from random args too
                    new_call.args = [a for a in BiOpaqueUtils.get_random_args(tree)
                                     if not isinstance(a, ast.Starred)]
                setattr(bogus, name, new_call)
            if isinstance(bogus, ast.Assign) and name == 'value':
                args = BiOpaqueUtils.get_possible_args(tree)
                # ★ Double-filter: no Starred in assignment values
                safe_args = [a for a in args if not isinstance(a, ast.Starred)]
                if safe_args:
                    new_value = random.choice(safe_args)
                    if isinstance(bogus.value, ast.List) or isinstance(bogus.value, ast.Dict):
                        new_value = ast.List(elts=[random.choice(safe_args)
                                                   for _ in range(random.randint(2, 6))])
                    setattr(bogus, name, new_value)
            if isinstance(bogus, ast.AugAssign) and name == 'value':
                args = BiOpaqueUtils.get_possible_args(tree)
                # ★ Double-filter: no Starred in aug-assignment values
                safe_args = [a for a in args if not isinstance(a, ast.Starred)]
                if safe_args:
                    new_value = random.choice(safe_args)
                    if isinstance(bogus.value, ast.List) or isinstance(bogus.value, ast.Dict):
                        new_value = ast.List(elts=[random.choice(safe_args)
                                                   for _ in range(random.randint(2, 6))])
                    setattr(bogus, name, new_value)
                    setattr(bogus, 'op', random.choice([ast.Add(), ast.Sub(), ast.Div(),
                            ast.Mult(), ast.BitXor(), *([node.op] * 3)]))
        return bogus

    def generate_roadline(goal: int):
        num = random.randint(1, 100)
        current_num = num
        roadline = []
        iterations = 0
        while current_num != goal and iterations < 1000:
            iterations += 1
            if current_num > goal:
                val = random.randint(1, num + 1)
                current_num -= val
                roadline.append([ast.Sub(), val])
            elif current_num < goal:
                val = random.randint(1, num + 1)
                current_num += val
                roadline.append([ast.Add(), val])
        return (num, roadline)

    def obscure_bool(value: bool, arg_name: str):
        roadline = BiOpaqueUtils.generate_roadline(value)
        attempts = 0
        while len(roadline[1]) > 6 and attempts < 100:
            roadline = BiOpaqueUtils.generate_roadline(value)
            attempts += 1
        original_number = roadline[0]
        roadline = roadline[1]
        binop_name = Utils.randomize_name(BiOpaqueUtils.alphabet, BiOpaqueUtils.length)
        binop = ast.Name(id=binop_name)
        for action in roadline:
            key = random.randint(1, 6996)
            xored_binop = ast.BinOp(left=ast.Constant(action[1] ^ key), op=ast.BitXor(), right=ast.Constant(value=key))
            binop = ast.BinOp(
                left=binop, op=action[0],
                right=ast.Call(
                    func=ast.Lambda(
                        args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                        body=xored_binop
                    ), args=[], keywords=[]
                )
            )
        if BiOpaqueUtils.safe_mode:
            return (ast.Call(
                func=ast.Lambda(
                    args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=binop_name)], kwonlyargs=[], kw_defaults=[], defaults=[]),
                    body=binop
                ), args=[ast.Constant(value=original_number)], keywords=[]
            ), None)
        return (ast.Call(
            func=ast.Lambda(
                args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=binop_name)], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=binop
            ), args=[ast.Name(id=arg_name)], keywords=[]
        ), original_number)

    def generate_opaquepredicate(tree, node, arg_name: str):
        test = BiOpaqueUtils.obscure_bool(True, arg_name)
        ret_node = ast.If(test=test[0], body=[node], orelse=[BiOpaqueUtils.generate_bogus_body(tree, node)])
        if Utils.get_chance() > 50:
            test = BiOpaqueUtils.obscure_bool(False, arg_name)
            ret_node.body, ret_node.orelse = ret_node.orelse, ret_node.body
            ret_node.test = test[0]
        return (ret_node, test[1])

    def fix_calls(tree, func_name: str, arg_name: str, value: int):
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Lambda):
                        continue
                    elif isinstance(child.func, ast.Name):
                        if child.func.id == func_name:
                            child.args.append(ast.Constant(value=value))
                    elif isinstance(child.func, ast.Attribute):
                        if child.func.attr == func_name:
                            child.args.append(ast.Constant(value=value))


class BiOpaqueTransformer():
    def __init__(self, alphabet: str, length: int, safe_mode: bool):
        BiOpaqueUtils.alphabet = alphabet
        BiOpaqueUtils.length = length
        BiOpaqueUtils.safe_mode = safe_mode

    def proceed(self, tree: ast.Module):
        self.tree = tree
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node
        biopaque = BiOpaqueTransformer._BiOpaqueTransformerInner(self.tree)
        self.tree = biopaque.visit(self.tree)
        self.tree = ast.parse(ast.unparse(tree))
        return self.tree

    class _BiOpaqueTransformerInner(ast.NodeTransformer):
        def __init__(self, tree: ast.Module):
            self.tree = tree

        def visit_FunctionDef(self, node: ast.FunctionDef):
            if isinstance(node, list):
                return node
            if node.args.vararg is not None or node.args.kwarg is not None:
                return node
            if node.name.startswith("__"):
                return node
            body = node.body
            body_length = len(body)
            bad_list = [ast.Global, ast.If, ast.For, ast.Return, ast.Pass, ast.Try, ast.ExceptHandler]
            chance = 75
            chance_step = int(50 / max(body_length, 1))
            if body_length == 1:
                return node
            for i in range(body_length):
                child = body[i]
                if isinstance(child, list):
                    continue
                if chance <= 0 or chance >= 100:
                    break
                if Utils.get_chance() > chance and not type(child) in bad_list:
                    arg_name = Utils.randomize_name(BiOpaqueUtils.alphabet, BiOpaqueUtils.length)
                    predicate = BiOpaqueUtils.generate_opaquepredicate(self.tree, child, arg_name)
                    if not BiOpaqueUtils.safe_mode:
                        node.args.args.append(ast.arg(arg=arg_name))
                        BiOpaqueUtils.fix_calls(self.tree, node.name, arg_name, predicate[1])
                    body[i] = predicate[0]
                    chance += chance_step
            return node


def _gen_opaque_zero_ast():
    """Generates an AST node evaluating to 0 at runtime using non-literal invariant constructs that break static AST constant folding (TRX-AST-B1)."""
    kind = _trx_rand(4)
    if kind == 0:
        k_val = _trx_rand(300) + 12
        return ast.BinOp(
            left=ast.BinOp(
                left=ast.BinOp(left=ast.Constant(value=k_val), op=ast.Pow(), right=ast.Constant(value=3)),
                op=ast.Sub(),
                right=ast.Constant(value=k_val)
            ),
            op=ast.Mod(),
            right=ast.Constant(value=6)
        )
    elif kind == 1:
        return ast.BinOp(
            left=ast.Call(
                func=ast.Name(id='len'),
                args=[ast.Attribute(value=ast.Call(func=ast.Name(id='type'), args=[ast.Constant(value=0)], keywords=[]), attr='__name__')],
                keywords=[]
            ),
            op=ast.Sub(),
            right=ast.Constant(value=3)
        )
    elif kind == 2:
        n_val = _trx_rand(300) + 15
        return ast.BinOp(
            left=ast.BinOp(
                left=ast.Constant(value=n_val),
                op=ast.Mult(),
                right=ast.BinOp(left=ast.Constant(value=n_val), op=ast.Add(), right=ast.Constant(value=1))
            ),
            op=ast.Mod(),
            right=ast.Constant(value=2)
        )
    else:
        x_val = _trx_rand(0xFFFF) + 200
        return ast.BinOp(
            left=ast.Constant(value=x_val),
            op=ast.BitAnd(),
            right=ast.UnaryOp(op=ast.Invert(), operand=ast.Constant(value=x_val))
        )


class MutatorUtils:
    alphabet = ""
    length = 16
    safe_mode = False

    def generate_stack_elts(real: int):
        elts = [ast.Constant(value=random.randint(0xFF * len(str(str(real))) * 100, 0xFFFFFF * len(str(str(real))) * 10)) for _ in range(random.randint(0, 15))]
        elts.append(ast.Constant(value=real))
        random.shuffle(elts)
        index = -1
        for elt in elts:
            if elt.value == real:
                index = elts.index(elt)
        return [elts, index]

    def proceed_int_assign(node: ast.Assign, ladder: int):
        old_value = node.value.value
        name = Utils.randomize_name(MutatorUtils.alphabet, MutatorUtils.length)
        keys = [~(random.randint(0xFF, 0xFFFFFFF)) for _ in range(ladder)]
        obscured = old_value
        for key in keys:
            obscured = obscured ^ ~(key)
        elts = MutatorUtils.generate_stack_elts(obscured)
        stack = ast.Assign(targets=[ast.Name(id=name)], value=ast.List(elts=elts[0]), lineno=None)
        key_index = random.randint(0xFF, 0xFFFFFFF)
        node.value.value = elts[1] ^ key_index
        name_obj = node.targets[0]
        body = []
        for key in keys:
            body.append(ast.Assign(
                targets=[ast.Subscript(value=ast.Name(id=name), slice=ast.BinOp(left=ast.Constant(value=key_index), op=ast.BitXor(), right=name_obj))],
                value=ast.BinOp(
                    left=ast.Subscript(value=ast.Name(id=name), slice=ast.BinOp(left=ast.Constant(value=key_index), op=ast.BitXor(), right=name_obj)),
                    op=ast.BitXor(),
                    right=ast.UnaryOp(op=ast.Invert(), operand=ast.Constant(value=key))
                ), lineno=None
            ))
        body.append(ast.Assign(
            targets=node.targets,
            value=ast.Subscript(value=ast.Name(id=name), slice=ast.BinOp(left=ast.Constant(value=key_index), op=ast.BitXor(), right=name_obj)),
            lineno=None
        ))
        return [node, stack, body]

    def generate_binopt_int(value: int, keys):
        obscured_value = value
        for key in keys:
            obscured_value ^= key
        binopt = ast.BinOp(left=ast.Constant(value=obscured_value), op=ast.BitXor(), right=ast.Constant(value=keys[0]))
        for key in keys:
            if keys[0] == key:
                continue
            binopt = ast.BinOp(left=binopt, op=ast.BitXor(), right=ast.Constant(value=key))
        binopt = ast.BinOp(left=binopt, op=ast.BitXor(), right=_gen_opaque_zero_ast())
        return binopt

    def generate_binopt_float(value: float, keys):
        obscured_value = value
        point_len = len(str(value).split('.')[1])
        for key in keys:
            obscured_value += key
        binopt = ast.BinOp(left=ast.Constant(value=obscured_value), op=ast.Sub(), right=ast.Constant(value=keys[0]))
        for key in keys:
            if keys[0] == key:
                continue
            binopt = ast.BinOp(left=binopt, op=ast.Sub(), right=ast.Constant(value=key))
        binopt = ast.Call(func=ast.Name(id='round'), args=[binopt, ast.Constant(value=point_len)], keywords=[])
        return binopt

    def proceed_int_constant(node: ast.Constant, ladder):
        keys = [random.randint(-0xFFFFFFFFF, 0xFFFFFFFFF) for _ in range(ladder)]
        name = Utils.randomize_name(MutatorUtils.alphabet, MutatorUtils.length)
        node = ast.Call(
            func=ast.Lambda(
                args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=name)], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=ast.Call(func=ast.Name(id=name), args=[], keywords=[])
            ),
            args=[ast.Lambda(
                args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=MutatorUtils.generate_binopt_int(node.value, keys)
            )], keywords=[]
        )
        return node

    def proceed_float_constant(node: ast.Constant, ladder):
        keys = [random.uniform(0xFFFF, 0xFFFFFFFFF) for _ in range(ladder)]
        name = Utils.randomize_name(MutatorUtils.alphabet, MutatorUtils.length)
        node = ast.Call(
            func=ast.Lambda(
                args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=name)], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=ast.Call(func=ast.Name(id=name), args=[], keywords=[])
            ),
            args=[ast.Lambda(
                args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=MutatorUtils.generate_binopt_float(node.value, keys)
            )], keywords=[]
        )
        return node


class ExceptionJumpUtils:
    alphabet = ""
    length = 16

    @staticmethod
    def _sparse_keys(count: int) -> list:
        # Sparse dispatcher states - source: Tr0ngX veli-3 ControlFlowUtils scheme
        # backported into the veli>=2 exception-jump dispatcher so state values are
        # non-contiguous and cannot be recovered by sorting indices (research note:
        # sequential 1..n dispatchers are trivially re-serializable by analysts,
        # cf. ObfuXtreme ControlFlowFlattener analysis, research_repos).
        keys = []
        seen = set()
        guard = 0
        while len(keys) < count and guard < count * 200 + 1000:
            guard += 1
            k = _trx_rand(0xFFFFFFF) + 1024
            if k in seen:
                continue
            seen.add(k)
            keys.append(k)
        return keys

    def generate_junk(ex_name: str, max_val: int):
        cases = []
        line = max_val + 1
        for i in range(random.randint(0, 3)):
            case_name = Utils.randomize_name(ExceptionJumpUtils.alphabet, ExceptionJumpUtils.length)
            cases.append(ast.If(
                test=ast.Compare(
                    left=ast.Subscript(value=ast.Attribute(value=ast.Name(id=ex_name), attr='args'), slice=ast.Constant(value=0)),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=line)]
                ),
                body=[ast.Assign(targets=[ast.Name(id=case_name)], value=ast.Constant(value=random.randint(0xFFFFF, 0xFFFFFFFFFFFF)), lineno=None)],
                orelse=[]
            ))
            line += 1
        return cases

    def generate_blockV(body):
        old_body = list(body)
        if not old_body:
            return []
        var_name = Utils.randomize_name(ExceptionJumpUtils.alphabet, ExceptionJumpUtils.length)
        ex_name = Utils.randomize_name(ExceptionJumpUtils.alphabet, ExceptionJumpUtils.length)
        # NOTE: Global/Nonlocal declarations are treated as regular flow statements
        # here (declaration semantics are scope-wide regardless of textual position),
        # matching pre-existing behavior of this helper.
        keys = ExceptionJumpUtils._sparse_keys(len(old_body))
        sentinel = max(keys) + _trx_rand(0xFFFF) + 17
        body.append(ast.Assign(targets=[ast.Name(id=var_name)], value=ast.Constant(value=keys[0]), lineno=None))
        case = ast.While(
            test=ast.Compare(left=ast.Name(id=var_name), ops=[ast.NotEq()], comparators=[ast.Constant(value=sentinel)]),
            body=[
                ast.Try(
                    body=[ast.Raise(exc=ast.Call(func=ast.Name(id='VELIMATIX'), args=[ast.Name(id=var_name)], keywords=[]))],
                    handlers=[ast.ExceptHandler(type=ast.Name(id='VELIMATIX'), name=ex_name, body=[])],
                    orelse=[], finalbody=[]
                )
            ], orelse=[]
        )
        for idx, body_node in enumerate(old_body):
            nxt = keys[idx + 1] if idx + 1 < len(keys) else sentinel
            case.body[0].handlers[0].body.append(ast.If(
                test=ast.Compare(
                    left=ast.Subscript(value=ast.Attribute(value=ast.Name(id=ex_name), attr='args'), slice=ast.Constant(value=0)),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=keys[idx])]
                ),
                body=[body_node,
                      ast.Assign(targets=[ast.Name(id=var_name)], value=ast.Constant(value=nxt), lineno=None)],
                orelse=[]
            ))
        junk = ExceptionJumpUtils.generate_junk(ex_name, 0xFFFFFFF)
        case.body[0].handlers[0].body.extend(junk)
        random.shuffle(case.body[0].handlers[0].body)
        body.append(case)
        return body

    def generate_block(node):
        old_body = node.body
        node.body = []
        var_name = Utils.randomize_name(ExceptionJumpUtils.alphabet, ExceptionJumpUtils.length)
        ex_name = Utils.randomize_name(ExceptionJumpUtils.alphabet, ExceptionJumpUtils.length)
        case = ast.While(
            test=ast.Compare(left=ast.Name(id=var_name), ops=[ast.NotEq()], comparators=[ast.Constant(value=1)]),
            body=[
                ast.Try(
                    body=[ast.Raise(exc=ast.Call(func=ast.Name(id='VELIMATIX'), args=[ast.Name(id=var_name)], keywords=[]))],
                    handlers=[ast.ExceptHandler(type=ast.Name(id='VELIMATIX'), name=ex_name, body=[])],
                    orelse=[], finalbody=[]
                )
            ], orelse=[]
        )
        decls = []
        flow_stmts = []
        # FIX (correctness): ast.Nonlocal hoisted to function top alongside Global -
        # relocating a nonlocal declaration inside try>handler>if is scoping-unsafe
        # (lesson source: ObfuXtreme BLOCKED-set analysis, research_repos).
        for body_node in old_body:
            if isinstance(body_node, (ast.Global, ast.Nonlocal)):
                decls.append(body_node)
            else:
                flow_stmts.append(body_node)
        if not flow_stmts:
            node.body = old_body
            return node
        keys = ExceptionJumpUtils._sparse_keys(len(flow_stmts))
        sentinel = max(keys) + _trx_rand(0xFFFF) + 17
        node.body.append(ast.Assign(targets=[ast.Name(id=var_name)], value=ast.Constant(value=keys[0]), lineno=None))
        case.body[0] = ast.Try(
            body=[ast.Raise(exc=ast.Call(func=ast.Name(id='VELIMATIX'), args=[ast.Name(id=var_name)], keywords=[]))],
            handlers=[ast.ExceptHandler(type=ast.Name(id='VELIMATIX'), name=ex_name, body=[])],
            orelse=[], finalbody=[]
        )
        case.test = ast.Compare(left=ast.Name(id=var_name), ops=[ast.NotEq()], comparators=[ast.Constant(value=sentinel)])
        for idx, body_node in enumerate(flow_stmts):
            nxt = keys[idx + 1] if idx + 1 < len(keys) else sentinel
            case.body[0].handlers[0].body.append(ast.If(
                test=ast.Compare(
                    left=ast.Subscript(value=ast.Attribute(value=ast.Name(id=ex_name), attr='args'), slice=ast.Constant(value=0)),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=keys[idx])]
                ),
                body=[body_node,
                      ast.Assign(targets=[ast.Name(id=var_name)], value=ast.Constant(value=nxt), lineno=None)],
                orelse=[]
            ))
        junk = ExceptionJumpUtils.generate_junk(ex_name, 0xFFFFFFF)
        case.body[0].handlers[0].body.extend(junk)
        random.shuffle(case.body[0].handlers[0].body)
        node.body.append(case)
        for decl in decls:
            node.body.insert(0, decl)
        return node


class ExceptionJumpTransformer():
    def __init__(self, alphabet: str, length: int):
        ExceptionJumpUtils.alphabet = alphabet
        ExceptionJumpUtils.length = length

    def proceed(self, tree: ast.Module):
        self.tree = tree
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node
        renamer = ExceptionJumpTransformer._ExceptionJumpInner()
        self.tree = renamer.visit(self.tree)
        return self.tree

    class _ExceptionJumpInner(ast.NodeTransformer):
        @staticmethod
        def _has_break_or_continue(node) -> bool:
            for child in ast.walk(node):
                if isinstance(child, (ast.Break, ast.Continue)):
                    return True
            return False

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            return node

        def visit_FunctionDef(self, node: ast.FunctionDef):
            # Skip if contains yield, yield from, or await (coroutine/generator)
            for child in ast.walk(node):
                if isinstance(child, (ast.Yield, ast.YieldFrom, ast.Await)):
                    return node
            if self._has_break_or_continue(node):
                return node
            node = ExceptionJumpUtils.generate_block(node)
            return node

        def visit_If(self, node: ast.If):
            if self._has_break_or_continue(node):
                return node
            node = ExceptionJumpUtils.generate_block(node)
            return node

        def visit_Assign(self, node: ast.Assign):
            if self._has_break_or_continue(node):
                return node
            node = ExceptionJumpUtils.generate_blockV([node])
            return node


class ControlFlowUtils:
    alphabet, length = "", 16

    def generate_junk_controlflow_block(maps, max_val, node: ast.FunctionDef):
        cases = []
        for i in range(random.randint(0, 3)):
            num = random.randint(1, max_val)
            attempts = 0
            while num in maps and attempts < 100:
                num = random.randint(1, max_val)
                attempts += 1
            case_name = Utils.randomize_name(ControlFlowUtils.alphabet, ControlFlowUtils.length)
            _junk_const = ast.Constant(value=num)
            _junk_const._no_mutate = True
            case = ast.match_case(
                pattern=ast.MatchValue(value=_junk_const),
                body=[ast.Assign(targets=[ast.Name(id=case_name)], value=ast.Constant(value=random.randint(0xFFFFF, 0xFFFFFFFFFFFF)), lineno=None)]
            )
            fixed_body = node.body
            if len(fixed_body) > 1:
                choice = random.choice(fixed_body)
                if isinstance(choice, (ast.Global, ast.Nonlocal)):
                    choice = ast.Pass()
                elif isinstance(choice, list):
                    choice = ast.Pass()
                elif isinstance(choice, ast.Expr) and isinstance(choice.value, ast.Call):
                    # Skip call expressions that might contain lambdas
                    choice = ast.Pass()
                else:
                    choice = copy.deepcopy(choice)
                case.body.append(choice)
            cases.append(case)
        return cases

    def generate_controlflow_block(node):
        old_body = node.body
        current = Utils.generate_next_num(0, 0xFFFF)
        next_num = Utils.generate_next_num(current, 0xFFFFFFFFFFFFFF)
        maps = []
        global_list = []
        turn_name = Utils.randomize_name(ControlFlowUtils.alphabet, ControlFlowUtils.length)
        base = [
            ast.Assign(targets=[ast.Name(id=turn_name)], value=ast.Constant(value=current), lineno=None),
            ast.While(
                test=ast.Compare(left=ast.Name(id=turn_name), ops=[ast.Lt()], comparators=[ast.Constant(value=0xFFFFFFFFFFFFFF + 1)]),
                body=[], orelse=[]
            )
        ]
        new_base = ast.Match(subject=ast.Name(id=turn_name), cases=[])
        for body_node in old_body:
            if isinstance(body_node, ast.Global):
                global_list.append(body_node)
                continue
            pattern_const = ast.Constant(value=current)
            pattern_const._no_mutate = True
            new = ast.match_case(pattern=ast.MatchValue(value=pattern_const), body=[body_node])
            if len(old_body) > 1:
                new.body.append(ast.Assign(targets=[ast.Name(id=turn_name)], value=ast.Constant(value=next_num), lineno=None))
            new_base.cases.append(new)
            maps.append(next_num)
            current = next_num
            next_num = Utils.generate_next_num(current, 0xFFFFFFFFFFFFFFFF)
        base[1].test.comparators[0].value = next_num
        new_base.cases[len(new_base.cases) - 1].body.append(ast.Break())
        junk_cases = ControlFlowUtils.generate_junk_controlflow_block(maps + [base[0].value.value], next_num, node)
        new_base.cases.extend(junk_cases)
        random.shuffle(new_base.cases)
        base[1].body.append(new_base)
        for global_def in global_list:
            base.insert(0, global_def)
        node.body = base


class CallUtils:
    def get_object_for_letter(letter):
        # SPLIT-FIX: same builtins-module resolution as get_possible_functions
        # above - a dict `__builtins__` would leak unresolvable dunder method
        # names into generated artifacts.
        objs = dir(_builtins_mod)
        random.shuffle(objs)
        for obj in objs:
            if letter in obj and hasattr(getattr(_builtins_mod, obj), '__name__') and getattr(_builtins_mod, obj).__name__ == obj and ('exception' in obj.lower() or 'error' in obj.lower() or '__' in obj.lower()):
                return [obj, obj.find(letter)]
        return None

    def generate_builtin_attr_block(node: ast.Call):
        name = node.func.id
        block = ast.Call(
            func=ast.Call(
                func=ast.Name(id="__import__('builtins').getattr"),
                args=[
                    ast.Name(id='__builtins__'),
                    ast.Call(func=ast.Attribute(value=ast.Constant(value=''), attr='join'), args=[ast.List(elts=[])], keywords=[])
                ], keywords=[]
            ),
            args=node.args, keywords=node.keywords
        )
        for letter in name:
            obj = CallUtils.get_object_for_letter(letter)
            if obj:
                block.func.args[1].args[0].elts.append(
                    ast.Subscript(value=ast.Attribute(value=ast.Name(id=obj[0]), attr='__name__'), slice=ast.Constant(value=obj[1]))
                )
            else:
                # Fallback: use letter directly if no builtin found
                block.func.args[1].args[0].elts.append(ast.Constant(value=letter))
        return block


class CallTransformer():
    def proceed(self, tree: ast.Module):
        self.tree = tree
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node
        call = CallTransformer._CallTransformerInner()
        self.tree = call.visit(self.tree)
        return self.tree

    class _CallTransformerInner(ast.NodeTransformer):
        SAFE_BUILTIN_CALLS = frozenset({
            'abs', 'aiter', 'all', 'any', 'bin', 'bool', 'bytearray', 'bytes',
            'callable', 'chr', 'complex', 'dict', 'divmod', 'enumerate', 'filter',
            'float', 'format', 'frozenset', 'getattr', 'hasattr', 'hash', 'hex',
            'int', 'isinstance', 'issubclass', 'iter', 'len', 'list', 'map', 'max',
            'min', 'next', 'oct', 'ord', 'pow', 'print', 'range', 'repr',
            'reversed', 'round', 'set', 'setattr', 'slice', 'sorted', 'str', 'sum',
            'tuple', 'type', 'zip',
        })

        def visit_Call(self, node: ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ('super', 'locals', 'eval', 'exec', '__import__'):
                    return node
                is_builtin = str(node.func.id) in self.SAFE_BUILTIN_CALLS
                if is_builtin:
                    if isinstance(__builtins__, dict):
                        is_builtin = node.func.id in __builtins__
                    else:
                        is_builtin = hasattr(__builtins__, node.func.id)
                    if is_builtin:
                        return CallUtils.generate_builtin_attr_block(node)
            return node


# ═══════════════════════════════════════════════════════════════
# CONTROL FLOW FLATTENING - MATCH-CASE STATE MACHINE (VELIMATIX)
# ═══════════════════════════════════════════════════════════════

class ControlFlowTransformer():
    def __init__(self, alphabet: str, length: int):
        ControlFlowUtils.alphabet = alphabet
        ControlFlowUtils.length = length

    def proceed(self, tree: ast.Module):
        self.tree = tree
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node
        transformer = ControlFlowTransformer._Inner(self.tree)
        self.tree = transformer.visit(self.tree)
        return self.tree

    class _Inner(ast.NodeTransformer):
        def __init__(self, tree):
            self.tree = tree

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            return node

        def visit_FunctionDef(self, node: ast.FunctionDef):
            if node.name.startswith('__'):
                return node
            # Skip if contains yield, yield from, or await (coroutine/generator)
            for child in ast.walk(node):
                if isinstance(child, (ast.Yield, ast.YieldFrom, ast.Await)):
                    return node
            if len(node.body) <= 1:
                return node
            real_stmts = [n for n in node.body if not isinstance(n, (ast.Global, ast.Nonlocal))]
            if len(real_stmts) <= 1:
                return node
            try:
                ControlFlowUtils.generate_controlflow_block(node)
            except Exception:
                pass
            return node


# ═══════════════════════════════════════════════════════════════
# CONSTANT MUTATOR - XOR CHAIN + LAMBDA WRAP (VELIMATIX)
# ═══════════════════════════════════════════════════════════════

class MutatorTransformer():
    def __init__(self, alphabet: str, length: int, ladder: int = 3):
        MutatorUtils.alphabet = alphabet
        MutatorUtils.length = length
        self.ladder = ladder

    def proceed(self, tree: ast.Module):
        self.tree = tree
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node
        transformer = MutatorTransformer._Inner(self.ladder)
        self.tree = transformer.visit(self.tree)
        return self.tree

    class _Inner(ast.NodeTransformer):
        def __init__(self, ladder):
            self.ladder = ladder
            self._depth = 0

        def visit_Constant(self, node: ast.Constant):
            if self._depth > 0:
                return node
            # Skip if marked as no_mutate
            if getattr(node, '_no_mutate', False):
                return node
            # Skip if parent is MatchValue or match_case
            if hasattr(node, 'parent') and isinstance(node.parent, (ast.MatchValue, ast.match_case)):
                return node
            # Also skip if any ancestor is a match_case pattern
            if hasattr(node, 'parent'):
                p = node.parent
                while hasattr(p, 'parent'):
                    if isinstance(p, ast.MatchValue):
                        return node
                    if isinstance(p, ast.match_case) and hasattr(p, 'pattern'):
                        try:
                            if node in ast.walk(p.pattern):
                                return node
                        except Exception:
                            pass
                    p = p.parent
            try:
                if isinstance(node.value, bool):
                    return node
                if isinstance(node.value, int) and abs(node.value) > 0 and abs(node.value) < 0xFFFFFFF:
                    if random.random() > 0.4:
                        self._depth += 1
                        result = MutatorUtils.proceed_int_constant(node, self.ladder)
                        self._depth -= 1
                        return result
                elif isinstance(node.value, float) and abs(node.value) < 0xFFFFFFF:
                    if random.random() > 0.6:
                        self._depth += 1
                        result = MutatorUtils.proceed_float_constant(node, self.ladder)
                        self._depth -= 1
                        return result
            except Exception:
                pass
            return node


# ═══════════════════════════════════════════════════════════════
# METHOD CLONER - FAKE FUNCTION COPIES (VELIMATIX)
# ═══════════════════════════════════════════════════════════════

class MethodClonerTransformer():
    """Injects fake copies of real functions with swapped bodies"""
    def __init__(self, alphabet: str, length: int, count: int = 5):
        self.alphabet = alphabet
        self.length = length
        self.count = count

    def proceed(self, tree: ast.Module):
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node

        funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and not n.name.startswith('__')]
        if len(funcs) < 1:
            return tree

        clones = []
        for _ in range(min(self.count, len(funcs) * 2)):
            source = random.choice(funcs)
            clone_name = Utils.randomize_name(self.alphabet, self.length)

            decoy_body = []
            if len(funcs) > 1:
                donor = random.choice(funcs)
                for stmt in donor.body[:random.randint(1, max(1, len(donor.body)))]:
                    try:
                        decoy_body.append(ast.parse(ast.unparse(stmt)).body[0])
                    except Exception:
                        decoy_body.append(ast.Pass())
            if not decoy_body:
                decoy_body = [ast.Pass()]

            junk_var = Utils.randomize_name(self.alphabet, self.length)
            decoy_body.insert(0, ast.Assign(
                targets=[ast.Name(id=junk_var)],
                value=ast.BinOp(
                    left=ast.Constant(value=random.randint(0, 0xFFFFFF)),
                    op=random.choice([ast.BitXor(), ast.Add(), ast.Sub()]),
                    right=ast.Constant(value=random.randint(0, 0xFFFFFF))
                ), lineno=None
            ))

            clone = ast.FunctionDef(
                name=clone_name,
                args=ast.arguments(
                    posonlyargs=[], args=[ast.arg(arg=Utils.randomize_name(self.alphabet, 8)) for _ in range(random.randint(0, 3))],
                    kwonlyargs=[], kw_defaults=[], defaults=[]
                ),
                body=decoy_body,
                decorator_list=[],
                returns=None,
                lineno=None
            )
            clones.append(clone)

        for clone in clones:
            pos = random.randint(0, len(tree.body))
            tree.body.insert(pos, clone)

        return tree


# ═══════════════════════════════════════════════════════════════
# BUILTIN RENAMER - OBFUSCATE ALL BUILTIN REFERENCES (VELIMATIX)
# ═══════════════════════════════════════════════════════════════

class BuiltinRenamerTransformer():
    """Rename ALL builtin references to random names with runtime mapping"""

    EXTRA_BUILTINS = [
        'sum', 'sorted', 'round', 'repr', 'pow', 'oct', 'next', 'min', 'max',
        'iter', 'issubclass', 'id', 'hash', 'hasattr', 'format',
        'divmod', 'delattr', 'breakpoint', 'bin', 'ascii', 'any', 'all',
        'abs', 'hex', 'reversed', 'quit', 'exit', 'enumerate', 'compile',
        'globals', 'float', 'frozenset', 'filter', 'complex', 'classmethod',
        'staticmethod', 'property', 'object', 'memoryview', 'zip',
        'slice', 'set', 'tuple', 'dict', 'open', 'list',
        'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError',
        'AttributeError', 'ImportError', 'RuntimeError', 'StopIteration',
        'FileNotFoundError', 'PermissionError', 'OSError', 'IOError',
        'NameError', 'SyntaxError', 'ZeroDivisionError', 'OverflowError',
        'UnicodeDecodeError', 'UnicodeEncodeError', 'ModuleNotFoundError',
        'KeyboardInterrupt', 'SystemExit', 'EOFError', 'NotImplementedError',
        'RecursionError', 'MemoryError', 'ConnectionError', 'TimeoutError',
    ]

    def __init__(self, alphabet: str, length: int):
        self.alphabet = alphabet
        self.length = length
        self.mapping = {}

    def proceed(self, tree: ast.Module):
        for builtin_name in self.EXTRA_BUILTINS:
            try:
                if isinstance(__builtins__, dict):
                    exists = builtin_name in __builtins__
                else:
                    exists = hasattr(__builtins__, builtin_name)
                if exists:
                    # Verify builtin actually exists before mapping
                    try:
                        if isinstance(__builtins__, dict):
                            _ = __builtins__[builtin_name]
                        else:
                            _ = getattr(__builtins__, builtin_name)
                        self.mapping[builtin_name] = Utils.randomize_name(self.alphabet, self.length)
                    except Exception:
                        pass
            except Exception:
                continue

        bound_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(getattr(node, 'ctx', None), (ast.Store, ast.Del)):
                bound_names.add(node.id)
            elif isinstance(node, ast.arg):
                bound_names.add(node.arg)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bound_names.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    bound_names.add((alias.asname or alias.name).split('.')[0])
            elif isinstance(node, ast.ExceptHandler) and node.name:
                bound_names.add(node.name)
            elif isinstance(node, ast.NamedExpr):
                bound_names.add(node.target.id)
            elif isinstance(node, ast.Global) or isinstance(node, ast.Nonlocal):
                bound_names.update(node.names)
        for shadowed in list(self.mapping.keys()):
            if shadowed in bound_names:
                del self.mapping[shadowed]

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(getattr(node, 'ctx', None), ast.Load) and node.id in self.mapping:
                node.id = self.mapping[node.id]

        xor_key = _trx_rand(200) + 55
        setup_stmts = []
        for original, renamed in self.mapping.items():
            try:
                # Verify builtin actually exists before generating code
                if isinstance(__builtins__, dict):
                    _ = __builtins__[original]
                else:
                    _ = getattr(__builtins__, original)
                enc_bytes = [b ^ xor_key for b in original.encode('utf-8')]
                # Dynamic stealth resolver with zero plaintext string literals
                res_expr = f"{renamed} = getattr(__import__('builtins'), bytes([_b ^ {xor_key} for _b in {enc_bytes}]).decode('utf-8'))"
                stmt = ast.parse(res_expr).body[0]
                setup_stmts.append(stmt)
                if "_DEBUG_MAP" in globals():
                    _DEBUG_MAP["renamed_builtins"][original] = renamed
            except (KeyError, AttributeError):
                # Remove from mapping if builtin doesn't actually exist
                continue

        # Inject Decoy Trap Builtin variables (anti-analysis honeypots)
        decoy_names = ['_sys_guard', '_eval_lock', '_mem_sec', '_debug_trap', '_ast_sig']
        for dname in decoy_names:
            rand_trap_id = Utils.randomize_name(self.alphabet, self.length)
            decoy_expr = f"{rand_trap_id} = (lambda *a, **k: None)"
            setup_stmts.append(ast.parse(decoy_expr).body[0])

        random.shuffle(setup_stmts)
        tree.body = setup_stmts + tree.body
        return tree



# ======================================================================
# (slice gap filler)
# ======================================================================

# ═══════════════════════════════════════════════════════════════
# DEAD CODE INJECTOR - REALISTIC JUNK (VELIMATIX)
# ═══════════════════════════════════════════════════════════════

class DeadCodeInjector():
    """Injects realistic-looking dead code that never executes"""
    def __init__(self, alphabet: str, length: int, density: int = 5):
        self.alphabet = alphabet
        self.length = length
        self.density = density

    def _gen_dead_block(self):
        var1 = Utils.randomize_name(self.alphabet, self.length)
        var2 = Utils.randomize_name(self.alphabet, self.length)
        var3 = Utils.randomize_name(self.alphabet, self.length)

        k_val = random.randint(11, 9999)
        impossible = random.choice([
            # Fermat / Euler invariant: (k^3 - k) % 3 != 0 is ALWAYS FALSE for any integer k
            ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=k_val), op=ast.Pow(), right=ast.Constant(value=3)),
                        op=ast.Sub(),
                        right=ast.Constant(value=k_val)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=3)
                ),
                ops=[ast.NotEq()],
                comparators=[ast.Constant(value=0)]
            ),
            # Parity invariant: (k^2 + k) % 2 != 0 is ALWAYS FALSE for any integer k
            ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=k_val), op=ast.Pow(), right=ast.Constant(value=2)),
                        op=ast.Add(),
                        right=ast.Constant(value=k_val)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=2)
                ),
                ops=[ast.NotEq()],
                comparators=[ast.Constant(value=0)]
            ),
            # Odd square modulo 8 invariant: ((2*k + 1)^2) % 8 == 0 is ALWAYS FALSE (always 1)
            ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(
                            left=ast.BinOp(left=ast.Constant(value=k_val), op=ast.Mult(), right=ast.Constant(value=2)),
                            op=ast.Add(),
                            right=ast.Constant(value=1)
                        ),
                        op=ast.Pow(),
                        right=ast.Constant(value=2)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=8)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)]
            ),
            # Non-negative square invariant: (k^2 + 1) < 0 is ALWAYS FALSE
            ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(left=ast.Constant(value=k_val), op=ast.Pow(), right=ast.Constant(value=2)),
                    op=ast.Add(),
                    right=ast.Constant(value=1)
                ),
                ops=[ast.Lt()],
                comparators=[ast.Constant(value=0)]
            ),
            ast.Call(func=ast.Name(id='isinstance'), args=[ast.Constant(value=0), ast.Name(id='str')], keywords=[]),
        ])

        body_choices = [
            [ast.Assign(targets=[ast.Name(id=var1)], value=ast.BinOp(
                left=ast.Constant(value=random.randint(0, 0xFFFF)),
                op=random.choice([ast.Add(), ast.BitXor(), ast.Mult()]),
                right=ast.Constant(value=random.randint(0, 0xFFFF))
            ), lineno=None)],
            [ast.Assign(targets=[ast.Name(id=var1)], value=ast.List(elts=[
                ast.Constant(value=random.randint(0, 0xFF)) for _ in range(random.randint(3, 8))
            ]), lineno=None),
             ast.Expr(value=ast.Call(func=ast.Attribute(value=ast.Name(id=var1), attr='append'),
                                     args=[ast.Constant(value=random.randint(0, 0xFFFF))], keywords=[]))],
            [ast.Assign(targets=[ast.Name(id=var1)], value=ast.Constant(value=random.randint(0, 0xFFFFFF)), lineno=None),
             ast.AugAssign(target=ast.Name(id=var1), op=ast.BitXor(),
                           value=ast.Constant(value=random.randint(0, 0xFFFF)))],
            [ast.Expr(value=ast.Call(func=ast.Name(id='str'), args=[
                ast.BinOp(left=ast.Constant(value=random.randint(0, 999)),
                           op=ast.Add(), right=ast.Constant(value=random.randint(0, 999)))
            ], keywords=[]))],
        ]

        return ast.If(test=impossible, body=random.choice(body_choices), orelse=[])

    def proceed(self, tree: ast.Module):
        new_body = []
        for node in tree.body:
            new_body.append(node)
            if random.random() < (self.density / 10.0):
                for _ in range(random.randint(1, 3)):
                    new_body.append(self._gen_dead_block())
        tree.body = new_body

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith('__'):
                injected = []
                for stmt in node.body:
                    injected.append(stmt)
                    if random.random() < (self.density / 15.0):
                        injected.append(self._gen_dead_block())
                node.body = injected

        return tree


# ═══════════════════════════════════════════════════════════════
# STRING ENCODER - BYTEWISE XOR (VELIMATIX STYLE)
# ═══════════════════════════════════════════════════════════════

class StringEncoderTransformer():
    """Encode string constants using bytewise XOR operations"""
    def __init__(self):
        self._depth = 0

    def proceed(self, tree: ast.Module):
        _skip_ids = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.match_case) and hasattr(n, 'pattern') and n.pattern:
                for child in ast.walk(n.pattern):
                    _skip_ids.add(id(child))
            if isinstance(n, ast.arg) and hasattr(n, 'annotation') and n.annotation:
                for child in ast.walk(n.annotation):
                    _skip_ids.add(id(child))
            if isinstance(n, ast.AnnAssign) and hasattr(n, 'annotation') and n.annotation:
                for child in ast.walk(n.annotation):
                    _skip_ids.add(id(child))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and hasattr(n, 'returns') and n.returns:
                for child in ast.walk(n.returns):
                    _skip_ids.add(id(child))
            if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and hasattr(n, 'decorator_list'):
                for d in n.decorator_list:
                    for child in ast.walk(d):
                        _skip_ids.add(id(child))

        transformer = StringEncoderTransformer._Inner(_skip_ids)
        tree = transformer.visit(tree)
        return tree

    class _Inner(ast.NodeTransformer):
        def __init__(self, skip_ids=None):
            self._depth = 0
            self._skip_ids = skip_ids or set()

        def visit_Constant(self, node: ast.Constant):
            if self._depth > 0:
                return node
            if id(node) in self._skip_ids:
                return node
            if not isinstance(node.value, str):
                return node
            if hasattr(node, 'parent') and isinstance(node.parent, ast.MatchValue):
                return node
            if len(node.value) == 0 or len(node.value) > 100:
                return node
            if random.random() > 0.6:
                return node

            try:
                self._depth += 1
                s = node.value
                magic = random.randint(1000000, 9999999)
                parts = []
                for ch in s:
                    logic = random.randint(1, 4)
                    key = ord(ch)
                    if logic == 1:
                        key3 = ~key ^ ~magic
                        parts.append(f"chr(~({key3} ^ ~{magic}))")
                    elif logic == 2:
                        shift = random.randint(1, 12)
                        key3 = key << shift
                        parts.append(f"chr({key3} >> {shift})")
                    elif logic == 3:
                        key3 = key + magic
                        parts.append(f"chr({key3} - {magic})")
                    else:
                        key3 = key * magic
                        parts.append(f"chr({key3} // {magic})")

                code = f"(lambda: ''.join([{', '.join(parts)}]))()"
                result = ast.parse(code, mode='eval').body
                self._depth -= 1
                return result
            except Exception:
                self._depth -= 1
                return node


class ObfuscatorSettings:
    def __init__(self):
        self.transformers = []

    def add_transformer(self, transformer):
        self.transformers.append(transformer)

    def exceptionjmp_transformer(self, alphabet: str, length: int):
        self.add_transformer(ExceptionJumpTransformer(alphabet, length))

    def call_transformer(self):
        self.add_transformer(CallTransformer())

    def biopaque_transformer(self, alphabet: str, length: int, safe_mode: bool):
        self.add_transformer(BiOpaqueTransformer(alphabet, length, safe_mode))

    def controlflow_transformer(self, alphabet: str, length: int):
        self.add_transformer(ControlFlowTransformer(alphabet, length))

    def mutator_transformer(self, alphabet: str, length: int, ladder: int = 3):
        self.add_transformer(MutatorTransformer(alphabet, length, ladder))

    def method_cloner(self, alphabet: str, length: int, count: int = 5):
        self.add_transformer(MethodClonerTransformer(alphabet, length, count))

    def builtin_renamer(self, alphabet: str, length: int):
        self.add_transformer(BuiltinRenamerTransformer(alphabet, length))

    def dead_code(self, alphabet: str, length: int, density: int = 5):
        self.add_transformer(DeadCodeInjector(alphabet, length, density))

    def string_encoder(self):
        self.add_transformer(StringEncoderTransformer())


def OBF_Spam(code, level=2):
    """Apply ALL Velimatix transformers with configurable intensity"""
    alphabet = "Ox" + ''.join(random.choices([str(i) for i in range(10)], k=6))
    length = 17

    try:
        setting = ast.parse(code)
        setting = ast.unparse(setting)
    except Exception:
        return code

    # ★ FIX: Prepend VELIMATIX class when ExceptionJump will be used
    if level >= 2:
        setting = "class VELIMATIX(MemoryError): pass\n" + setting

    for pass_num in range(level):
        BiOpaqueUtils.possible_args = []
        BiOpaqueUtils.possible_functions = []

        settings = ObfuscatorSettings()

        settings.biopaque_transformer(alphabet, length, safe_mode=True)
        settings.call_transformer()

        if level >= 2:
            settings.exceptionjmp_transformer(alphabet, length)
            settings.dead_code(alphabet, length, density=3 + pass_num)

        if level >= 3:
            settings.controlflow_transformer(alphabet, length)
            settings.mutator_transformer(alphabet, length, ladder=2 + pass_num)
            settings.method_cloner(alphabet, length, count=3 + pass_num * 2)
            settings.string_encoder()

        try:
            tree = ast.parse(setting)
            for transformer in settings.transformers:
                try:
                    tree = transformer.proceed(tree)
                except Exception:
                    pass
            setting = ast.unparse(tree)

            # ★ FIX: Re-prepend after each pass for same reason
            if level >= 2:
                setting = "class VELIMATIX(MemoryError): pass\n" + setting

        except Exception:
            break

    return setting


def _render_fstring_template(node: ast.JoinedStr):
    parts = []
    args = []

    def render(joined: ast.JoinedStr) -> str:
        seg_parts = []
        for value in joined.values:
            if isinstance(value, ast.FormattedValue):
                idx = len(args)
                args.append(value.value)
                seg = "{" + str(idx)
                if value.conversion is not None and value.conversion != -1:
                    seg += "!" + chr(value.conversion)
                if value.format_spec is not None:
                    if isinstance(value.format_spec, ast.JoinedStr):
                        seg += ":" + render(value.format_spec)
                    elif isinstance(value.format_spec, ast.Constant) and isinstance(value.format_spec.value, str):
                        spec_text = str(value.format_spec.value).replace("{", "{{").replace("}", "}}")
                        seg += ":" + spec_text
                seg += "}"
                seg_parts.append(seg)
            elif isinstance(value, ast.Constant) and isinstance(value.value, str):
                seg_parts.append(str(value.value).replace("{", "{{").replace("}", "}}"))
        return "".join(seg_parts)

    return render(node), args


class OBF_Formatter(ast.NodeTransformer):
    """Convert f-strings to .format() calls"""
    def visit_JoinedStr(self, node: ast.JoinedStr) -> ast.Call:
        template, args = _render_fstring_template(node)
        return ast.Call(
            func=ast.Attribute(value=ast.Constant(value=template), attr="format", ctx=ast.Load()),
            args=args,
            keywords=[]
        )


def OBF_Import(code):
    """Convert import statements to __import__ calls"""
    imports_ = []
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                imports_.append(name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            for name in node.names:
                if name.name == '*':
                    imports_.append((module, '*'))
                else:
                    imports_.append((module, name.name, name.asname))
    result_lines = code.splitlines()
    for i, line in enumerate(result_lines):
        if line.startswith('import') or line.startswith('from'):
            result_lines[i] = ''
    for imp in imports_:
        if isinstance(imp, tuple):
            if imp[1] == '*':
                result_lines.insert(0, f'from {imp[0]} import *')
            elif imp[2]:
                result_lines.insert(0, f"{imp[2]} = getattr(__import__({imp[0]!r}, fromlist=[{imp[1]!r}]), {imp[1]!r})")
            else:
                result_lines.insert(0, f"{imp[1]} = getattr(__import__({imp[0]!r}, fromlist=[{imp[1]!r}]), {imp[1]!r})")
        else:
            as_target = imp.asname if imp.asname else imp.name
            result_lines.insert(0, f"{as_target} = __import__({imp.name!r})")
    return '\n'.join(result_lines)

def _velimatix_obf(code, mode=2):
    """Apply FULL Velimatix engine based on mode level
    Mode 1: BiOpaque + CallObf + DeadCode
    Mode 2: + ExceptionJump + Import obf + BuiltinRename
    Mode 3: + ControlFlow + Mutator + MethodClone + StringEncode + Multi-pass
    """
    try:
        tree = ast.parse(code)
        tree = OBF_Formatter().visit(tree)
        code = ast.unparse(tree)

        if mode >= 2:
            try:
                code = OBF_Import(code)
            except Exception:
                pass

        code = "class VELIMATIX(MemoryError): pass\n" + code

        passes = 1
        alphabet = "Ox" + ''.join(random.choices([str(i) for i in range(10)], k=6))
        length = 17

        for pass_num in range(passes):
            BiOpaqueUtils.possible_args = []
            BiOpaqueUtils.possible_functions = []

            settings = ObfuscatorSettings()

            settings.biopaque_transformer(alphabet, length, safe_mode=True)
            settings.call_transformer()
            settings.dead_code(alphabet, length, density=3)

            if mode >= 2:
                settings.exceptionjmp_transformer(alphabet, length)
                if pass_num == 0:
                    settings.builtin_renamer(alphabet, length)

            if mode >= 3:
                settings.controlflow_transformer(alphabet, length)
                settings.mutator_transformer(alphabet, length, ladder=2 + pass_num)
                settings.method_cloner(alphabet, length, count=4)
                settings.string_encoder()

            try:
                tree = ast.parse(code)
                for transformer in settings.transformers:
                    try:
                        tree = transformer.proceed(tree)
                    except Exception:
                        continue
                code = ast.unparse(tree)

                # ★ FIX: Always re-prepend VELIMATIX class at the very top
                # after each pass. BuiltinRenamer pushes 60+ Assign nodes
                # above the old class def; on the next pass ExceptionJump
                # wraps those assigns with raise VELIMATIX(...) — which
                # fails because VELIMATIX isn't defined yet.
                # Re-prepending guarantees VELIMATIX is defined before
                # any ExceptionJump block can reference it.
                if mode >= 2:
                    code = "class VELIMATIX(MemoryError): pass\n" + code

            except Exception:
                break

        return code
    except Exception as e:
        return code


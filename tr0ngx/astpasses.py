# AUTO-SPLIT from tr0ngx_obfuscator.py (mechanical slice, imports pending repair)
import ast
import random
import secrets
import string

from .names import rd, _rd, _trx_rand, _trx_choice, randomint
from . import config as _cfg
from . import diagnostics as _diag
from . import names as _names

# ═══════════════════════════════════════════════════════════════
# NUMBER-THEORETIC MATHEMATICAL OPAQUE PREDICATES (MODULE B)
# ═══════════════════════════════════════════════════════════════

class MathOpaqueTransformer(ast.NodeTransformer):
    """Injects number-theoretic opaque invariants (Quadratic Non-Residues mod 7, Coprimality, Euler) to force path explosion in symbolic execution / SMT solvers (TRX-AST-B4/FEAT-002)."""

    def __init__(self, alphabet: str = None, length: int = 12):
        self.alphabet = alphabet or string.ascii_lowercase
        self.length = length

    def _gen_opaque_true_test(self) -> ast.AST:
        """Generates an expression that is mathematically proven to be ALWAYS TRUE at runtime.

        Predicate families (7): QNR mod 7, Fermat/Euler k^3-k, n(n+1) parity,
        Carmichael composites (Fermat pseudoprime for ALL bases), MBA bitwise
        identity (x+y == (x^y)+2(x&y)), Collatz odd-step parity, modular inverse
        via Fermat little theorem. Family breadth modeled after the opaque-predicate
        library in bedrock-obfuscator (Apache-2.0, research note); implementation
        here is independent.
        """
        pick = _trx_rand(7)
        if pick == 0:
            x_val = _trx_rand(1000) + 11
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(left=ast.Constant(value=x_val), op=ast.Mult(), right=ast.Constant(value=x_val)),
                    op=ast.Mod(),
                    right=ast.Constant(value=7)
                ),
                ops=[ast.NotEq()],
                comparators=[ast.Constant(value=3)]
            )
        elif pick == 1:
            k_val = _trx_rand(500) + 13
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=k_val), op=ast.Pow(), right=ast.Constant(value=3)),
                        op=ast.Sub(),
                        right=ast.Constant(value=k_val)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=6)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)]
            )
        elif pick == 2:
            n_val = _trx_rand(500) + 9
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.Constant(value=n_val),
                        op=ast.Mult(),
                        right=ast.BinOp(left=ast.Constant(value=n_val), op=ast.Add(), right=ast.Constant(value=1))
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=2)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)]
            )
        elif pick == 3:
            # Carmichael number: a^n ≡ a (mod n) holds for EVERY integer a when n
            # is a Carmichael composite (561, 1105, 1729, 2465, 2821, 6601).
            carmichael = (561, 1105, 1729, 2465, 2821, 6601)[_trx_rand(6)]
            base = _trx_rand(97) + 2
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=base), op=ast.Pow(), right=ast.Constant(value=carmichael)),
                        op=ast.Sub(),
                        right=ast.Constant(value=base)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=carmichael)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)]
            )
        elif pick == 4:
            # MBA identity: (x ^ y) + ((x & y) << 1) == x + y for all non-negative ints.
            a = _trx_rand(0xFFFFF) + 7
            b = _trx_rand(0xFFFFF) + 3
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(left=ast.Constant(value=a), op=ast.BitXor(), right=ast.Constant(value=b)),
                    op=ast.Add(),
                    right=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=a), op=ast.BitAnd(), right=ast.Constant(value=b)),
                        op=ast.LShift(),
                        right=ast.Constant(value=1)
                    )
                ),
                ops=[ast.Eq()],
                comparators=[ast.BinOp(left=ast.Constant(value=a), op=ast.Add(), right=ast.Constant(value=b))]
            )
        elif pick == 5:
            # Collatz odd step: for any odd m, (3m + 1) is even.
            m = 2 * (_trx_rand(9999) + 1) + 1
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=m), op=ast.Mult(), right=ast.Constant(value=3)),
                        op=ast.Add(),
                        right=ast.Constant(value=1)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=2)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)]
            )
        else:
            # Modular inverse via Fermat's little theorem: a * a^(p-2) ≡ 1 (mod p), p prime.
            p = (101, 103, 107, 109, 113, 127, 131, 137, 139, 149)[_trx_rand(10)]
            inv_a = _trx_rand(p - 2) + 2
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.Constant(value=inv_a),
                        op=ast.Mult(),
                        right=ast.BinOp(left=ast.Constant(value=inv_a), op=ast.Pow(), right=ast.Constant(value=p - 2))
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=p)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=1)]
            )

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.generic_visit(node)
        if node.name.startswith("__") or len(node.body) < 2:
            return node
        
        new_body = []
        for stmt in node.body:
            if _trx_rand(100) < 60 and not isinstance(stmt, (ast.Return, ast.Yield, ast.YieldFrom, ast.Global, ast.Nonlocal, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                bogus_var = rd('biopaque')
                bogus_stmt = ast.Assign(
                    targets=[ast.Name(id=bogus_var)],
                    value=ast.BinOp(
                        left=ast.Constant(value=_trx_rand(0xFFFFFF)),
                        op=ast.BitXor(),
                        right=ast.Constant(value=_trx_rand(0xFFFFFF))
                    ),
                    lineno=None
                )
                wrapped_if = ast.If(
                    test=self._gen_opaque_true_test(),
                    body=[stmt],
                    orelse=[bogus_stmt]
                )
                ast.copy_location(wrapped_if, stmt)
                ast.fix_missing_locations(wrapped_if)
                new_body.append(wrapped_if)
            else:
                new_body.append(stmt)
        node.body = new_body
        return node

def _math_opaque_obf(code_str: str) -> str:
    """Apply Number-Theoretic Mathematical Opaque Predicates to code."""
    tree = ast.parse(code_str)
    transformer = MathOpaqueTransformer()
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


# ═══════════════════════════════════════════════════════════════
# DYNAMIC PER-CALLSITE STRING XOR ENCRYPTION (MODULE C)
# ═══════════════════════════════════════════════════════════════

class DynamicStringXORTransformer(ast.NodeTransformer):
    """Replaces string literals with dynamic per-callsite XOR decryption expressions derived from AST coordinates (TRX-AST-B3/FEAT-003)."""

    def __init__(self, master_seed: int = None):
        self.master_seed = master_seed or (_trx_rand(0x7FFFFFFF) + 1000)
        self.protected_ids = set()

    @staticmethod
    def _collect_docstrings(tree) -> set:
        protected = set()
        for anc in ast.walk(tree):
            if isinstance(anc, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                body = getattr(anc, 'body', [])
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                    protected.add(id(body[0].value))
        return protected

    def visit_JoinedStr(self, node: ast.JoinedStr):
        # Do not descend into f-string expressions: pre-3.12 unparse cannot safely
        # re-nest quotes when string constants become Lambda calls (PEP 701 gate).
        return node

    def visit_match_case(self, node: ast.match_case):
        # In Python 3.10+, match patterns cannot contain Call/Lambda expressions
        for child in ast.walk(node.pattern):
            self.protected_ids.add(id(child))
        if node.guard:
            node.guard = self.visit(node.guard)
        node.body = [self.visit(stmt) for stmt in node.body]
        return node

    @staticmethod
    def _make_int_algebra_expr(value: int, site_key: int) -> ast.BinOp:
        """Exact integer reconstruction via (a ^ b) + c where c = value - (a ^ b).
        Strategy source: pyshield passes/constants.py int tiers (MIT, research note)."""
        a = (site_key % 0x7F) + 1
        b = ((site_key >> 7) % 0x7F) + 1
        c = value - (a ^ b)
        return ast.BinOp(
            left=ast.BinOp(left=ast.Constant(value=a), op=ast.BitXor(), right=ast.Constant(value=b)),
            op=ast.Add(),
            right=ast.Constant(value=c)
        )

    def _build_bytes_decode_lambda(self, payload_expr: ast.expr, elt_builder) -> ast.Call:
        """Shared anonymous-decoder shell: lambda s: bytes(<genexp over enumerate(s)>).decode('utf-8')."""
        v_s = _rd()
        v_i = _rd()
        v_b = _rd()
        return ast.Call(
            func=ast.Lambda(
                args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=v_s)], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=ast.Call(
                    func=ast.Attribute(
                        value=ast.Call(
                            func=ast.Name(id='bytes'),
                            args=[
                                ast.ListComp(
                                    elt=elt_builder(v_i, v_b),
                                    generators=[
                                        ast.comprehension(
                                            target=ast.Tuple(elts=[ast.Name(id=v_i), ast.Name(id=v_b)]),
                                            iter=ast.Call(func=ast.Name(id='enumerate'), args=[ast.Name(id=v_s)], keywords=[]),
                                            ifs=[], is_async=0
                                        )
                                    ]
                                )
                            ],
                            keywords=[]
                        ),
                        attr='decode'
                    ),
                    args=[ast.Constant(value='utf-8')],
                    keywords=[]
                )
            ),
            args=[payload_expr],
            keywords=[]
        )

    def visit_Constant(self, node: ast.Constant):
        if id(node) in self.protected_ids:
            return node
        # Exact float -> integer-ratio reconstruction. Source: pyshield
        # ConstantTransformer Fraction idea (MIT), hardened: Python floats carry an
        # EXACT rational via as_integer_ratio(), so n / d reproduces the ORIGINAL
        # float bit-for-bit (no limit_denominator approximation drift).
        if isinstance(node.value, float) and not isinstance(node.value, bool):
            try:
                ratio_n, ratio_d = node.value.as_integer_ratio()
            except (OverflowError, ValueError):
                return node
            if abs(ratio_n) < (1 << 62) and ratio_d.bit_length() <= 62 and ratio_d != 0:
                lineno_f = getattr(node, 'lineno', 1) or 1
                col_f = getattr(node, 'col_offset', 0) or 0
                fkey = (self.master_seed ^ (lineno_f * 31337) ^ (col_f * 101) ^ 0xF70A7) & 0xFFFFFFFF
                num_expr = self._make_int_algebra_expr(ratio_n, fkey)
                den_expr = self._make_int_algebra_expr(ratio_d, (fkey ^ 0x5A5A5A) & 0xFFFFFFFF)
                div_expr = ast.BinOp(left=num_expr, op=ast.Div(), right=den_expr)
                ast.copy_location(div_expr, node)
                ast.fix_missing_locations(div_expr)
                return div_expr
            return node
        if isinstance(node.value, str) and len(node.value) > 0:
            if (node.value.startswith("__") and node.value.endswith("__")) or len(node.value) > 20000:
                return node
            
            val_bytes = node.value.encode('utf-8')
            lineno = getattr(node, 'lineno', 1) or 1
            col_offset = getattr(node, 'col_offset', 0) or 0
            
            site_key = (self.master_seed ^ (lineno * 31337) ^ (col_offset * 101) ^ len(val_bytes)) & 0xFFFFFFFF

            # Weighted per-callsite cipher heterogeneity - source: pyshield
            # DistributedStringEncryptor dispatcher (MIT, research note): three
            # structurally distinct inline schemes so no single deobfuscation
            # pattern can sweep every callsite.
            strat_pick = site_key % 100
            if strat_pick < 50:
                strategy = 'coord_xor'      # legacy rolling coordinate keystream
            elif strat_pick < 75:
                strategy = 'poly_affine'    # enc[i] = (b + salt*(i+1)) mod 256
            else:
                strategy = 'chunked_xor'    # single-key XOR + randomized chunk split

            if strategy == 'coord_xor':
                enc_bytes = bytearray()
                for idx, b in enumerate(val_bytes):
                    k_byte = (site_key + idx * 31337 + (idx ^ 0x5A)) & 0xFF
                    enc_bytes.append(b ^ k_byte)
                
                enc_bytes_list = list(enc_bytes)
                
                v_s = _rd()
                v_k = _rd()
                v_i = _rd()
                v_b = _rd()
                
                dec_expr = ast.Call(
                    func=ast.Lambda(
                        args=ast.arguments(
                            posonlyargs=[],
                            args=[ast.arg(arg=v_s), ast.arg(arg=v_k)],
                            kwonlyargs=[], kw_defaults=[], defaults=[]
                        ),
                        body=ast.Call(
                            func=ast.Attribute(
                                value=ast.Call(
                                    func=ast.Name(id='bytes'),
                                    args=[
                                        ast.ListComp(
                                            elt=ast.BinOp(
                                                left=ast.Name(id=v_b),
                                                op=ast.BitXor(),
                                                right=ast.BinOp(
                                                    left=ast.BinOp(
                                                        left=ast.BinOp(
                                                            left=ast.Name(id=v_k),
                                                            op=ast.Add(),
                                                            right=ast.BinOp(left=ast.Name(id=v_i), op=ast.Mult(), right=ast.Constant(value=31337))
                                                        ),
                                                        op=ast.Add(),
                                                        right=ast.BinOp(left=ast.Name(id=v_i), op=ast.BitXor(), right=ast.Constant(value=90))
                                                    ),
                                                    op=ast.BitAnd(),
                                                    right=ast.Constant(value=255)
                                                )
                                            ),
                                            generators=[
                                                ast.comprehension(
                                                    target=ast.Tuple(elts=[ast.Name(id=v_i), ast.Name(id=v_b)]),
                                                    iter=ast.Call(func=ast.Name(id='enumerate'), args=[ast.Name(id=v_s)], keywords=[]),
                                                    ifs=[],
                                                    is_async=0
                                                )
                                            ]
                                        )
                                    ],
                                    keywords=[]
                                ),
                                attr='decode'
                            ),
                            args=[ast.Constant(value='utf-8')],
                            keywords=[]
                        )
                    ),
                    args=[
                        ast.Call(func=ast.Name(id='bytes'), args=[ast.List(elts=[ast.Constant(value=x) for x in enc_bytes_list])], keywords=[]),
                        ast.Constant(value=site_key)
                    ],
                    keywords=[]
                )
                ast.copy_location(dec_expr, node)
                ast.fix_missing_locations(dec_expr)
                return dec_expr

            if strategy == 'poly_affine':
                salt = (site_key % 127) + 1
                enc_list = [(b + salt * (i + 1)) % 256 for i, b in enumerate(val_bytes)]
                payload = ast.Call(func=ast.Name(id='bytes'),
                                   args=[ast.List(elts=[ast.Constant(value=x) for x in enc_list])],
                                   keywords=[])

                def _unshift(i_name, b_name):
                    return ast.BinOp(
                        left=ast.BinOp(
                            left=ast.Name(id=b_name),
                            op=ast.Sub(),
                            right=ast.BinOp(
                                left=ast.Constant(value=salt),
                                op=ast.Mult(),
                                right=ast.BinOp(left=ast.Name(id=i_name), op=ast.Add(), right=ast.Constant(value=1))
                            )
                        ),
                        op=ast.Mod(),
                        right=ast.Constant(value=256)
                    )

                dec_expr = self._build_bytes_decode_lambda(payload, _unshift)
                ast.copy_location(dec_expr, node)
                ast.fix_missing_locations(dec_expr)
                return dec_expr

            # chunked_xor
            kb = ((site_key >> 7) & 0xFF) or 0x5B
            enc_full = bytes(b ^ kb for b in val_bytes)
            n_chunks = 2 + (site_key % 4)
            if len(enc_full) <= n_chunks:
                chunks = [enc_full]
            else:
                bounds = set()
                lcg = site_key | 1
                attempts = 0
                while len(bounds) < n_chunks - 1 and attempts < 64:
                    attempts += 1
                    lcg = (lcg * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
                    bounds.add((lcg >> 33) % (len(enc_full) - 1) + 1)
                cuts = [0] + sorted(bounds) + [len(enc_full)]
                chunks = [enc_full[cuts[k]:cuts[k + 1]] for k in range(len(cuts) - 1)]
            chunk_nodes = []
            for ch in chunks:
                if not ch:
                    continue
                chunk_nodes.append(ast.Call(func=ast.Name(id='bytes'),
                                            args=[ast.List(elts=[ast.Constant(value=x) for x in ch])],
                                            keywords=[]))
            if not chunk_nodes:
                chunk_nodes.append(ast.Call(func=ast.Name(id='bytes'),
                                            args=[ast.List(elts=[])], keywords=[]))
            joined = chunk_nodes[0]
            for extra in chunk_nodes[1:]:
                joined = ast.BinOp(left=joined, op=ast.Add(), right=extra)

            def _unxor(i_name, b_name):
                return ast.BinOp(
                    left=ast.Name(id=b_name),
                    op=ast.BitXor(),
                    right=ast.Constant(value=kb)
                )

            dec_expr = self._build_bytes_decode_lambda(joined, _unxor)
            ast.copy_location(dec_expr, node)
            ast.fix_missing_locations(dec_expr)
            return dec_expr
        return node

def _dyn_strings_obf(code_str: str, seed: int = None) -> str:
    """Apply Dynamic Per-Callsite String XOR Encryption."""
    tree = ast.parse(code_str)
    transformer = DynamicStringXORTransformer(master_seed=seed)
    transformer.protected_ids = transformer._collect_docstrings(tree)
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


# ═══════════════════════════════════════════════════════════════
# BEDROCK-GRADE DECOMPILER TRAP & SECRET SHARING ENGINES
# ═══════════════════════════════════════════════════════════════

def _ast_touches_exception_frames(node: ast.AST) -> bool:
    """Eligibility sniff (source: bedrock-obfuscator UnsupportedOpcode gates,
    Apache-2.0 research note): True when the subtree produces CPython exception
    tables / frame setup at bytecode level. Conservative transforms skip these
    units - silent wrong output is strictly worse than skipping a transform."""
    for child in ast.walk(node):
        if isinstance(child, (ast.Try, ast.With, ast.AsyncFor, ast.AsyncWith)):
            return True
        if hasattr(ast, 'TryStar') and isinstance(child, ast.TryStar):
            return True
    return False


class DecompilerTrapTransformer(ast.NodeTransformer):
    """Wraps AST statement blocks in opaque mathematical predicates and overlapping trap structures that break decompilers (uncompyle6/decompyle3/pycdc)."""

    def __init__(self, density: float = 0.5, seed: int = None):
        self.density = density
        self.rng = random.Random(seed or _trx_rand(0x7FFFFFFF))

    def _make_opaque_true(self):
        n_val = self.rng.randint(2, 9999)
        inv_type = self.rng.randint(0, 2)
        if inv_type == 0:
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=n_val), op=ast.Pow(), right=ast.Constant(value=2)),
                        op=ast.Add(),
                        right=ast.Constant(value=n_val)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=2)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)]
            )
        elif inv_type == 1:
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=n_val), op=ast.Pow(), right=ast.Constant(value=3)),
                        op=ast.Sub(),
                        right=ast.Constant(value=n_val)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=3)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)]
            )
        else:
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(left=ast.Constant(value=n_val), op=ast.Pow(), right=ast.Constant(value=2)),
                    op=ast.Add(),
                    right=ast.Constant(value=1)
                ),
                ops=[ast.Gt()],
                comparators=[ast.Constant(value=0)]
            )

    def _make_dead_trap_body(self):
        v_tmp = f"_trap_{self.rng.randint(1000, 99999)}"
        return [
            ast.While(
                test=ast.Constant(value=False),
                body=[
                    ast.Assign(targets=[ast.Name(id=v_tmp, ctx=ast.Store())], value=ast.Constant(value=0xDEADBEEF)),
                    ast.Expr(value=ast.Call(func=ast.Name(id="exit", ctx=ast.Load()), args=[ast.Constant(value=1)], keywords=[])),
                    ast.Break()
                ],
                orelse=[]
            )
        ]

    def _wrap_stmts(self, stmts):
        new_stmts = []
        for stmt in stmts:
            if isinstance(stmt, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Global, ast.Nonlocal)):
                new_stmts.append(self.visit(stmt))
            elif self.rng.random() < self.density and not isinstance(stmt, (ast.Return, ast.Yield, ast.YieldFrom, ast.Break, ast.Continue)):
                trap_if = ast.If(
                    test=self._make_opaque_true(),
                    body=[self.visit(stmt)],
                    orelse=self._make_dead_trap_body()
                )
                ast.copy_location(trap_if, stmt)
                new_stmts.append(trap_if)
            else:
                new_stmts.append(self.visit(stmt))
        return new_stmts

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Eligibility gate: leave exception-table-producing functions untouched.
        if _ast_touches_exception_frames(node):
            return node
        node.body = self._wrap_stmts(node.body)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        if _ast_touches_exception_frames(node):
            return node
        node.body = self._wrap_stmts(node.body)
        return node

    def visit_Module(self, node: ast.Module):
        node.body = self._wrap_stmts(node.body)
        return node

def _dec_trap_obf(code_str: str, density: float = 0.5, seed: int = None) -> str:
    """Apply Decompiler Control Flow Trapping Matrix."""
    tree = ast.parse(code_str)
    transformer = DecompilerTrapTransformer(density=density, seed=seed)
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


class VariableSplittingTransformer(ast.NodeTransformer):
    """Splits local integer assignments into XOR secret shares (s1 ^ s2) dynamically inside functions."""

    def __init__(self, seed: int = None):
        self.rng = random.Random(seed or _trx_rand(0x7FFFFFFF))

    def visit_Assign(self, node: ast.Assign):
        if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) 
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, int) 
                and not isinstance(node.value.value, bool)
                and not node.targets[0].id.startswith("__")):
            val = node.value.value
            mask = self.rng.randint(1, 0xFFFFFF)
            s1 = mask
            s2 = val ^ mask
            node.value = ast.BinOp(
                left=ast.Constant(value=s1),
                op=ast.BitXor(),
                right=ast.Constant(value=s2)
            )
            return node
        return self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        if (isinstance(node.value, ast.Constant) and isinstance(node.value.value, int)
                and not isinstance(node.value.value, bool)):
            val = node.value.value
            mask = self.rng.randint(1, 0xFFFFFF)
            s1 = mask
            s2 = val ^ mask
            node.value = ast.BinOp(
                left=ast.Constant(value=s1),
                op=ast.BitXor(),
                right=ast.Constant(value=s2)
            )
            return node
        return self.generic_visit(node)

def _var_split_obf(code_str: str, seed: int = None) -> str:
    """Apply Integer Variable Secret Sharing Transformation."""
    tree = ast.parse(code_str)
    transformer = VariableSplittingTransformer(seed=seed)
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


class StringFragmentationTransformer(ast.NodeTransformer):
    """Fragments string literals >= 6 chars into XOR-encrypted pools with decoys and dynamic assembly (strfrag2)."""

    def __init__(self, seed: int = None):
        self.rng = random.Random(seed or _trx_rand(0x7FFFFFFF))
        self.key1 = self.rng.randint(1, 254)
        self.key2 = self.rng.randint(1, 254)
        self.fn_name = rd('biopaque')
        self.pool_name = rd('state_machine')
        self.final_pool = []
        self.protected_ids = set()

    def _xor_bytes(self, b_data: bytes, k: int) -> bytes:
        return bytes(b ^ k for b in b_data)

    def visit_JoinedStr(self, node: ast.JoinedStr):
        return node

    @staticmethod
    def _collect_protected(tree) -> set:
        protected = set()
        for anc in ast.walk(tree):
            if isinstance(anc, ast.match_case):
                for child in ast.walk(anc.pattern):
                    protected.add(id(child))
            elif isinstance(anc, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                body = getattr(anc, 'body', [])
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                    protected.add(id(body[0].value))
        return protected

    def _transform_string(self, node: ast.Constant):
        if isinstance(node.value, str) and len(node.value) >= 6 and not (node.value.startswith("__") and node.value.endswith("__")) and len(node.value) < 10000:
            raw_bytes = node.value.encode("utf-8")
            chunk_size = max(2, len(raw_bytes) // 3)
            chunks = [raw_bytes[i:i + chunk_size] for i in range(0, len(raw_bytes), chunk_size)]

            chunk_indices = []
            for ch in chunks:
                enc_ch = self._xor_bytes(ch, self.key1)
                idx = len(self.final_pool)
                self.final_pool.append(enc_ch)
                chunk_indices.append(idx ^ self.key2)

            call_expr = ast.Call(
                func=ast.Name(id=self.fn_name, ctx=ast.Load()),
                args=[
                    ast.List(elts=[ast.Constant(value=i) for i in chunk_indices], ctx=ast.Load()),
                    ast.Constant(value=self.key1)
                ],
                keywords=[]
            )
            return ast.copy_location(call_expr, node)
        return node

    def visit_match_case(self, node: ast.match_case):
        for child in ast.walk(node.pattern):
            self.protected_ids.add(id(child))
        node.body = [self.visit(stmt) for stmt in node.body]
        if node.guard is not None:
            node.guard = self.visit(node.guard)
        return node

    def visit_Constant(self, node: ast.Constant):
        if id(node) in self.protected_ids:
            return node
        return self._transform_string(node)

    def build_preamble(self) -> str:
        if not self.final_pool:
            return ""
        n_decoys = max(3, len(self.final_pool) // 3)
        for _ in range(n_decoys):
            decoy = bytes(self.rng.randint(0, 255) for _ in range(self.rng.randint(2, 8)))
            self.final_pool.append(self._xor_bytes(decoy, self.key1))

        pool_repr = "[" + ", ".join(repr(c) for c in self.final_pool) + "]"
        return f"""
{self.pool_name} = {pool_repr}
def {self.fn_name}(idxs, k):
    res = bytearray()
    for _i in idxs:
        chunk = {self.pool_name}[_i ^ {self.key2}]
        res.extend(b ^ k for b in chunk)
    return res.decode('utf-8', 'replace')
"""

def _str_frag_obf(code_str: str, seed: int = None) -> str:
    """Apply String Fragmentation and Dynamic Assembly."""
    tree = ast.parse(code_str)
    transformer = StringFragmentationTransformer(seed=seed)
    transformer.protected_ids = transformer._collect_protected(tree)
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)
    preamble = transformer.build_preamble()
    res_code = ast.unparse(tree)
    if preamble.strip():
        lines = res_code.split("\n")
        insert_at = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("from __future__ import"):
                insert_at = i + 1
            elif insert_at == 0 and (stripped.startswith("#") or stripped == ""):
                continue
            elif insert_at == 0:
                break
        lines.insert(insert_at, preamble.strip())
        return "\n".join(lines)
    return res_code

def _generate_debug_poison_shield() -> str:
    """Generate Deceptive Poison State Machine shield (Bedrock-grade silent degradation)."""
    fn_name = rd('state_machine')
    return f"""
# ═══ DECEPTIVE DEBUG POISON STATE MACHINE ═══
__trx_poison_state__ = [0]
def __trx_poison(weight, tag):
    global __trx_poison_state__
    _mix = int.from_bytes(__import__('hashlib').sha256(str(tag).encode()).digest()[:4], 'big')
    __trx_poison_state__[0] = ((__trx_poison_state__[0] << 5) ^ _mix ^ (weight * 0x45D9F3B)) & 0xFFFFFFFF

def {fn_name}():
    import sys
    if getattr(sys, 'gettrace', None) and sys.gettrace():
        __trx_poison(9, 'debugger_trace')
    if hasattr(sys, 'monitoring'):
        try:
            _mon = sys.monitoring
            for _tid in (1, 2, 3, 4, 5):
                if _mon.get_tool(_tid) is not None:
                    __trx_poison(8, 'sys_monitoring')
                    break
        except Exception:
            pass
try:
    {fn_name}()
except Exception:
    pass
"""

def _generate_spoof_meta_shield(target_module: str = "<frozen importlib._bootstrap>") -> str:
    """Generate Metadata Spoofing & Signature Debranding shield."""
    fn_name = rd('guard')
    return f"""
# ═══ METADATA SPOOFING & SIGNATURE DEBRANDING ═══
def {fn_name}():
    import sys
    try:
        if '__file__' in globals():
            globals()['__file__'] = '{target_module}'
        if __name__ in sys.modules:
            sys.modules[__name__].__file__ = '{target_module}'
    except Exception:
        pass
try:
    {fn_name}()
except Exception:
    pass
"""


# ═══════════════════════════════════════════════════════════════
# IN-MEMORY ANTI-DUMP & GC OBJECT SCRUBBING (MODULE D)
# ═══════════════════════════════════════════════════════════════

def _generate_anti_dump_shield() -> str:
    """Generate in-memory anti-dump shield, GC object scrubber, and code object metadata neutralizer (TRX-DEOB-009/FEAT-004)."""
    fn_name = rd('state_machine')
    abort_fn = rd('guard')
    
    return f'''
# ═══ IN-MEMORY ANTI-DUMP & GC SCANNER SCRUBBER ═══
def {fn_name}():
    import sys, gc, types, os

    def {abort_fn}():
        try:
            os._exit(1)
        except Exception:
            sys.exit(1)

    # 1. Neutralize / Filter gc.get_objects to hide code objects and frames from heap dumpers
    try:
        _orig_get_objects = gc.get_objects
        def _safe_get_objects():
            _objs = _orig_get_objects()
            return [_o for _o in _objs if not isinstance(_o, (types.CodeType, types.FrameType))]
        gc.get_objects = _safe_get_objects
    except Exception:
        pass

    # 2. Linux prctl(PR_SET_DUMPABLE, 0) to prevent /proc/pid/mem dumping & gdb attach
    if os.name == 'posix':
        try:
            import ctypes
            _libc = ctypes.CDLL(None)
            if hasattr(_libc, 'prctl'):
                _libc.prctl(4, 0, 0, 0, 0)
        except Exception:
            pass

    # 3. Background GC watchdog to detect inspection objects
    try:
        import threading, time
        def _dump_watchdog():
            _bad_modules = {{'objgraph', 'pympler', 'memory_profiler', 'guppy', 'heapy', 'frida', 'cheatengine'}}
            while True:
                try:
                    if set(sys.modules.keys()) & _bad_modules:
                        {abort_fn}()
                    time.sleep(1.0)
                except Exception:
                    pass
        _t = threading.Thread(target=_dump_watchdog, daemon=True)
        _t.start()
    except Exception:
        pass

try:
    {fn_name}()
except Exception:
    pass
'''



# ======================================================================
# (slice gap filler)
# ======================================================================

# ═══════════════════════════════════════════════════════════════
# DYNAMIC KEY DERIVATION - NOT HARDCODED
# ═══════════════════════════════════════════════════════════════

def _derive_key_code():
    """Generate code that derives key at runtime from environment"""
    salt = secrets.token_hex(16)
    return f"""
def _dk():
    import hashlib, sys, os, struct, platform
    parts = []
    parts.append(sys.version[:5].encode())
    parts.append(platform.python_implementation().encode())
    parts.append(b'{salt}')
    parts.append(str(sys.maxsize).encode())
    parts.append(sys.byteorder.encode())
    combined = b''.join(parts)
    return hashlib.sha256(combined).digest()
"""




# ═══════════════════════════════════════════════════════════════
# MULTI-STRATEGY STRING OBFUSCATION
# ═══════════════════════════════════════════════════════════════

def _chrobf(x):
    return ord(x) + 0xFF78FF

def obfstr(v, _depth=0):
    if v == "":
        return f"''"

    # Limit recursion depth to prevent stack overflow
    if _depth > 3:
        # Fallback to simple lambda chain
        x = [ord(c) + 0xFF78FF for c in v]
        return f"(lambda: globals()['{_join}'](globals()['{_list}'](globals()['{_map}'](globals()['{_hexrun}'], {x}))))()"

    strategy = random.randint(1, 6)

    if strategy == 1:
        # Lambda chain (original enhanced)
        x = [ord(c) + 0xFF78FF for c in v]
        _str_ = f"(lambda: globals()['{_join}'](globals()['{_list}'](globals()['{_map}'](globals()['{_hexrun}'], {x}))))()"
        return _str_

    elif strategy == 2:
        # Reverse + decode
        reversed_v = v[::-1]
        x = [ord(c) + 0xFF78FF for c in reversed_v]
        return f"(lambda: globals()['{_join}'](globals()['{_list}'](globals()['{_map}'](globals()['{_hexrun}'], {x})))[::-1])()"

    elif strategy == 3:
        # Recursive split (only for strings > 1 char)
        if len(v) <= 1:
            x = [ord(c) + 0xFF78FF for c in v]
            return f"(lambda: globals()['{_join}'](globals()['{_list}'](globals()['{_map}'](globals()['{_hexrun}'], {x}))))()"
        mid = len(v) // 2
        part1 = obfstr(v[:mid], _depth=_depth+1)
        part2 = obfstr(v[mid:], _depth=_depth+1)
        _a = rd()
        return f"(lambda: (lambda {_a}: {_a})({part1} + {part2}))()"

    elif strategy == 4:
        # XOR with random magic
        keys = []
        magic = _trx_rand(9000000) + 1000000
        for char in v:
            logic = _trx_rand(5) + 1
            key = ord(char)
            key2 = magic
            if logic == 1:
                key3 = key ^ magic
                keys.append(f"(lambda: chr({key3} ^ {key2}))()")
            elif logic == 2:
                shift = _trx_rand(12) + 1
                key3 = key << shift
                keys.append(f"(lambda: chr({key3} >> {shift}))()")
            elif logic == 3:
                key3 = key + magic
                keys.append(f"(lambda: chr({key3} - {key2}))()")
            elif logic == 4:
                key3 = key * magic
                keys.append(f"(lambda: chr({key3} // {key2}))()")
            else:
                # NOT + XOR
                key3 = ~key ^ ~magic
                keys.append(f"(lambda: chr(~({key3} ^ ~{magic})))()")
        return f"(lambda: ''.join([{', '.join(keys)}]))()"

    elif strategy == 5:
        # Bytewise encoding with shuffled indices
        indices = list(range(len(v)))
        shuffled = indices[:]
        # seeding-aware shuffle (SystemRandom ignored --seed; audit fix)
        if _names._SEEDED_RNG is not None:
            _names._SEEDED_RNG.shuffle(shuffled)
        else:
            secrets.SystemRandom().shuffle(shuffled)
        encoded = [(shuffled[i], ord(v[shuffled[i]]) + 0xFF78FF) for i in range(len(v))]
        pairs_str = str(encoded)
        return f"(lambda: ''.join(globals()['{_hexrun}'](c) for _, c in sorted({pairs_str})))()"

    else:
        # Multi-base encoding
        encoded_bytes = v.encode('utf-8')
        nums = [b for b in encoded_bytes]
        xor_val = _trx_rand(255) + 1
        xored = [n ^ xor_val for n in nums]
        return f"(lambda: bytes([x ^ {xor_val} for x in {xored}]).decode('utf-8'))()"


# ═══════════════════════════════════════════════════════════════
# MULTI-STRATEGY INTEGER OBFUSCATION
# ═══════════════════════════════════════════════════════════════

def _byte(v):
    byte_array = bytearray()
    byte_array.extend(v.to_bytes((v.bit_length() + 7) // 8, 'big'))
    return b"tr0ngx/" + byte_array

def obfint(v):
    n = rd()
    if 'bool' in str(type(v)):
        if str(v) == 'True':
            return f'(lambda: (lambda {n}: {n} + (lambda: H2SbF7({(1 + 0x7777)}))())(0) == 1)()'
        else:
            return f'(lambda: (lambda {n}: {n} - (lambda: H2SbF7(({(1 + 0x7777)})))())(0) == 1)()'
    else:
        strategy = _trx_rand(8) + 1
        val = int(v)

        # Strategy 1 (_byte) only works for non-negative integers
        if strategy == 1:
            if val >= 0:
                return f'(lambda: c2h6({_byte(val)}))()'
            else:
                # Fallback for negative numbers: use XOR strategy
                xor_key = _trx_rand(0xFFFFF - 0x1000) + 0x1000
                return f'(lambda: (lambda: {val ^ xor_key} ^ {xor_key})())()'

        elif strategy == 2:
            offset = _trx_rand(0xFFFFF - 0x5000) + 0x5000
            return f'(lambda: (lambda: {val + offset} - {offset})())()'

        elif strategy == 3:
            xor_key = _trx_rand(0xFFFFF - 0x1000) + 0x1000
            return f'(lambda: (lambda: {val ^ xor_key} ^ {xor_key})())()'

        elif strategy == 4:
            mult = _trx_choice([2, 3, 5, 7, 11, 13])
            remainder = val % mult
            base = val // mult
            return f'(lambda: (lambda: {base} * {mult} + {remainder})())()'

        elif strategy == 5:
            return f'(lambda: H2SbF7({(val + 0x7777)}))()'

        elif strategy == 6:
            return f'(lambda: ~~{val})()'

        elif strategy == 7:
            a = _trx_rand(10000) + 1
            b = val + a
            _p = rd()
            return f'(lambda: (lambda {_p}: {_p} - {a})({b}))()'

        else:
            # Bit shift reconstruction
            if val == 0:
                return f'(lambda: 0 >> 1)()'
            high = val >> 8
            low = val & 0xFF
            return f'(lambda: ({high} << 8) | {low})()'


def varsobf(v):
    r1, r2, r3, r4 = randomint(), randomint(), randomint(), randomint()
    _result = f"""({(v)}) if bool(bool(bool({(v)}))) < bool(type(int({r1})>int({r2})<int({r3})>int({r4}))) and bool(str(str({r1})>int({r2})<int({r3})>int({r4}))) > 2 else {v}"""
    try:
        # PERF: eval-mode parse validates the expression without building the
        # redundant Module+Assign wrapper nodes.
        ast.parse(_result, mode='eval')
        return _result
    except SyntaxError:
        return str(v)


# ═══════════════════════════════════════════════════════════════
# GLOBAL CHEMICAL VARIABLE NAMES
# ═══════════════════════════════════════════════════════════════

_join = "h2o"
_lambda = "ᅠ"
_int = "h2so4"
_str = "co2"
_bool = "mol"
_type = "feo2"
_bytes = "feso4"
_vars = "agno3"
_ip = "hno3"
ngoac = "{"
_ngoac = "}"
___import__ = "ch2oh4p2so4"
_movdiv = "h2"
_hexrun = "o2"
_argshexrun = "h2so3"
__print = r"tryᅠ"
__input = r"exceptᅠ"
_eval = "h2o3"
_list = "agno4"
_map = "h3o"
_exec = "nacl"
_chr = "hcl"
_ord = "naoh"
_len = "caso4"
_range = "fe2o3"
_getattr = "al2o3"
_setattr = "sio2"
_isinstance = "caco3"


def unicodeobf(x):
    return [ord(i) + 0xFF78FF for i in x]

def _uni(x):
    return unicodeobf(x)


__bool = rd()
__exx = rd()
_temp = rd()
_temp1 = rd()
_wt = rd()
_exp = rd()

# ═══════════════════════════════════════════════════════════════
# STATE MACHINE CONTROL FLOW FLATTENING
# ═══════════════════════════════════════════════════════════════

def _generate_state_machine(statements):
    """Convert sequential code into a state machine - hard to trace"""
    if not statements:
        return ""

    states = list(range(len(statements)))
    random.shuffle(states)

    state_var = rd()
    dispatch_var = rd()

    lines = []
    lines.append(f"{state_var} = {states[0]}")
    lines.append(f"while {state_var} != -1:")

    for original_idx, state_num in enumerate(states):
        next_state = states[original_idx + 1] if original_idx + 1 < len(states) else -1
        indent = "    "
        lines.append(f"{indent}if {state_var} == {state_num}:")

        if isinstance(statements[original_idx], str):
            for line in statements[original_idx].split('\n'):
                if line.strip():
                    lines.append(f"{indent}    {line.strip()}")
        else:
            lines.append(f"{indent}    {statements[original_idx]}")

        lines.append(f"{indent}    {state_var} = {next_state}")

    # Add junk states
    for _ in range(random.randint(3, 8)):
        junk_state = random.randint(1000, 9999)
        junk_var = rd()
        lines.append(f"    if {state_var} == {junk_state}:")
        lines.append(f"        {junk_var} = {random.randint(0, 0xFFFFFF)}")
        lines.append(f"        {state_var} = -1")

    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════
# CHUNKED EXECUTION ENGINE
# ═══════════════════════════════════════════════════════════════

def _generate_chunked_executor():
    """Generate code that decrypts and executes in chunks - never full code in RAM"""
    chunk_key_var = rd()
    chunk_data_var = rd()
    chunk_func = rd()
    decrypt_func = rd()

    return f"""
def {decrypt_func}(chunk, key_part):
    import hashlib
    dk = hashlib.sha256(key_part).digest()
    result = bytearray()
    for i, b in enumerate(chunk):
        result.append(b ^ dk[i % len(dk)])
    return bytes(result)

def {chunk_func}(chunks, keys):
    import marshal, types
    for i in range(len(chunks)):
        decrypted = {decrypt_func}(chunks[i], keys[i])
        code_obj = marshal.loads(decrypted)
        exec(code_obj)
        del decrypted, code_obj
"""

# ═══════════════════════════════════════════════════════════════
def _generate_var_block():
    global var
    var = fr"""

globals()['{_bool}'] = {varsobf('bool')}
globals()['{_str}'] = {varsobf('str')}
globals()['{_type}'] = {varsobf('type')}
globals()['{_int}'] = {varsobf('int')}
globals()['{_bytes}'] = {varsobf('bytes')}
globals()['{_vars}'] = {varsobf('vars')}
globals()['{_movdiv}'] = {varsobf('callable')}
globals()['{_eval}'] = {varsobf('eval')}
globals()['{_list}'] = {varsobf('list')}
globals()['{_map}'] = {varsobf('map')}
globals()['{_exec}'] = {varsobf('exec')}
globals()['{_chr}'] = {varsobf('chr')}
globals()['{_ord}'] = {varsobf('ord')}
globals()['{_len}'] = {varsobf('len')}
globals()['{_range}'] = {varsobf('range')}
globals()['{_getattr}'] = {varsobf('getattr')}
globals()['{_setattr}'] = {varsobf('setattr')}
globals()['{_isinstance}'] = {varsobf('isinstance')}

globals()['{___import__}'] = {varsobf('__import__')}

globals()['tryᅠ'] = {varsobf('print')}
globals()['exceptᅠ'] = {varsobf('input')}

def {_join}(july, *k):
    if k:
        tr0ngx = '+'
        op = "+"
    else:
        tr0ngx = ''
        op = ''
    globals()['{__exx}'] = {obfint(True)}
    globals()['{_join}'] = {_join}
    globals()['{_str}'] = {_str}
    globals()['july'] = july
    for globals()['tr0ngx_'] in globals()['july']:
        if not {__exx}:
            globals()['tr0ngx_'] += (lambda: '')()
        tr0ngx += {_str}(tr0ngx_)
        f = {obfint(True)}
    return tr0ngx

def H2SbF7(x):
    return globals()['{_int}'](x - 0x7777)

def c2h6(e):
    br = bytearray(e[globals()['{_len}'](b"tr0ngx/"):])
    r = 0
    for b in br:
        r = r * 256 + b
    return r

def longlongint(x):
    ar = []
    for i in x:
        ar.append(globals()['{_eval}'](i))
    return ar

if {obfint(True)}:
    def {_hexrun}({_argshexrun}):
        {_argshexrun} = {_argshexrun} - 0xFF78FF
        if {_argshexrun} <= 0x7F:
            return globals()['{_str}'](globals()['{_bytes}']([{_argshexrun}]), "utf8")
        elif {_argshexrun} <= 0x7FF:
            if 1 < 2:
                b1 = 0xC0 | ({_argshexrun} >> 6)
            b2 = 0x80 | ({_argshexrun} & 0x3F)
            return globals()['{_str}'](globals()['{_bytes}']([b1, b2]), "utf8")
        elif {_argshexrun} <= 0xFFFF:
            b1 = 0xE0 | ({_argshexrun} >> 12)
            if 2 > 1:
                b2 = 0x80 | (({_argshexrun} >> 6) & 0x3F)
            b3 = 0x80 | ({_argshexrun} & 0x3F)
            return globals()['{_str}'](globals()['{_bytes}']([b1, b2, b3]), "utf8")
        else:
            b1 = 0xF0 | ({_argshexrun} >> 18)
            if 2 == 2:
                b2 = 0x80 | (({_argshexrun} >> 12) & 0x3F)
            if 1 < 2 < 3:
                b3 = 0x80 | (({_argshexrun} >> 6) & 0x3F)
            b4 = 0x80 | ({_argshexrun} & 0x3F)
            return globals()['{_str}'](globals()['{_bytes}']([b1, b2, b3, b4]), "utf8")

    def _hex(j):
        {_argshexrun} = ''
        for _hex in j:
            {_argshexrun} += (globals()['{_hexrun}'](_hex))
        return {_argshexrun}
else:
    "tr0ngx"
"""
    return var

def _refresh_runtime_symbols():
    global _str, _bool, _type, _int, _bytes, _vars, _ip, ___import__, _movdiv, _hexrun, _argshexrun
    global _eval, _list, _map, _exec, _chr, _ord, _len, _range, _getattr, _setattr, _isinstance
    global _join, __bool, __exx, _temp, _temp1, _wt, _exp, var
    _str = rd()
    _bool = rd()
    _type = rd()
    _int = rd()
    _bytes = rd()
    _vars = rd()
    _ip = rd()
    ___import__ = rd()
    _movdiv = rd()
    _hexrun = rd()
    _argshexrun = rd()
    _eval = rd()
    _list = rd()
    _map = rd()
    _exec = rd()
    _chr = rd()
    _ord = rd()
    _len = rd()
    _range = rd()
    _getattr = rd()
    _setattr = rd()
    _isinstance = rd()
    _join = rd()
    __bool = rd()
    __exx = rd()
    _temp = rd()
    _temp1 = rd()
    _wt = rd()
    _exp = rd()
    _generate_var_block()

# NOTE (determinism fix): the legacy module-import-time call above made the var
# block bake OS entropy into a template BEFORE --seed could influence it, so two
# seeded processes produced different artifacts. The block is now regenerated
# inside obfuscate_single_target() AFTER per-file seeding; import-time call kept
# only as fallback for direct-API users that skip the pipeline entry.

# ═══════════════════════════════════════════════════════════════
# ANTI-PYCDC ENHANCED (COMPACT & FAST DECOMPILER KILLER)
# ═══════════════════════════════════════════════════════════════

antipycdc = ''
for i in range(120):
    antipycdc += f"你器(你器(你器(''))),"
antipycdc = "try:tr0ngx=[" + antipycdc + "]\nexcept:pass"

ANTI_PYCDC = f"""
def 你器(你):
    return 你
try:
    pass
except Exception:
    pass
finally:
    pass
{antipycdc}
"""


# ======================================================================
# (slice gap filler)
# ======================================================================

# ═══════════════════════════════════════════════════════════════
# AST TRANSFORMATION ENGINE - ENHANCED
# ═══════════════════════════════════════════════════════════════

def _moreobf(tree):
    """Enhanced AST obfuscation with junk code injection"""

    def rd_local():
        return str(random.randint(0x1E000000000, 0x7E000000000))

    def generate_junk_expr():
        junk_type = random.randint(1, 8)
        if junk_type == 1:
            return ast.Expr(value=ast.Call(
                func=ast.Name(id='str'),
                args=[ast.Constant(value=random.randint(0, 99999))],
                keywords=[]
            ))
        elif junk_type == 2:
            return ast.Expr(value=ast.Call(
                func=ast.Name(id='bool'),
                args=[ast.Constant(value=random.randint(0, 1))],
                keywords=[]
            ))
        elif junk_type == 3:
            return ast.Assign(
                targets=[ast.Name(id="_v_" + rd_local())],
                value=ast.Constant(value=random.randint(0, 0xFFFFFF)),
                lineno=None
            )
        elif junk_type == 4:
            return ast.Assign(
                targets=[ast.Name(id="_v_" + rd_local())],
                value=ast.BinOp(
                    left=ast.Constant(value=random.randint(1, 1000)),
                    op=random.choice([ast.Add(), ast.Sub(), ast.Mult(), ast.BitXor(), ast.BitOr()]),
                    right=ast.Constant(value=random.randint(1, 1000))
                ),
                lineno=None
            )
        elif junk_type == 5:
            return ast.Expr(value=ast.Call(
                func=ast.Name(id='type'),
                args=[ast.Constant(value=random.choice([0, '', [], None, True, False]))],
                keywords=[]
            ))
        elif junk_type == 6:
            # Junk if statement
            return ast.If(
                test=ast.Compare(
                    left=ast.Constant(value=random.randint(100, 999)),
                    ops=[ast.Gt()],
                    comparators=[ast.Constant(value=random.randint(1000, 9999))]
                ),
                body=[ast.Assign(
                    targets=[ast.Name(id="_v_" + rd_local())],
                    value=ast.Constant(value=None),
                    lineno=None
                )],
                orelse=[]
            )
        elif junk_type == 7:
            return ast.Expr(value=ast.Call(
                func=ast.Name(id='len'),
                args=[ast.Constant(value=secrets.token_hex(4))],
                keywords=[]
            ))
        else:
            return ast.Expr(value=ast.Call(
                func=ast.Name(id='int'),
                args=[ast.BinOp(
                    left=ast.Constant(value=random.randint(1, 100)),
                    op=ast.Add(),
                    right=ast.Constant(value=random.randint(1, 100))
                )],
                keywords=[]
            ))

    def junk(en, max_value):
        cases = []
        line = max_value + 1
        for i in range(random.randint(3, 8)):
            case_name = "_v_" + rd_local()
            case_body = [
                ast.If(
                    test=ast.Compare(
                        left=ast.Subscript(
                            value=ast.Attribute(value=ast.Name(id=en), attr='args'),
                            slice=ast.Constant(value=0)
                        ),
                        ops=[ast.Eq()],
                        comparators=[ast.Constant(value=line)]
                    ),
                    body=[
                        ast.Assign(
                            targets=[ast.Name(id=case_name)],
                            value=ast.Constant(value=random.randint(0xFFFFF, 0xFFFFFFFFFFFF)),
                            lineno=None
                        ),
                        generate_junk_expr(),
                    ],
                    orelse=[]
                )
            ]
            cases.extend(case_body)
            line += 1
        return cases

    def bl(body):
        var_name = "_v_" + rd_local()
        en = "_v_" + rd_local()

        tb = [
            ast.AugAssign(target=ast.Name(id=var_name), op=ast.Add(), value=ast.Constant(value=1)),
            ast.Try(
                body=[ast.Raise(exc=ast.Call(func=ast.Name(id='MemoryError'),
                                             args=[ast.Name(id=var_name)], keywords=[]))],
                handlers=[ast.ExceptHandler(type=ast.Name(id='MemoryError'), name=en, body=[])],
                orelse=[], finalbody=[]
            )
        ]

        for i in body:
            tb[1].handlers[0].body.append(
                ast.If(
                    test=ast.Compare(
                        left=ast.Subscript(
                            value=ast.Attribute(value=ast.Name(id=en), attr='args'),
                            slice=ast.Constant(value=0)
                        ),
                        ops=[ast.Eq()],
                        comparators=[ast.Constant(value=1)]
                    ),
                    body=[i], orelse=[]
                )
            )

        tb[1].handlers[0].body.extend(junk(en, len(body) + 1))
        pre_junk = [generate_junk_expr() for _ in range(random.randint(1, 3))]

        node = ast.Assign(targets=[ast.Name(id=var_name)], value=ast.Constant(value=0), lineno=None)
        return pre_junk + [node] + tb

    def _bl(node):
        olb = node.body
        var_name = "_v_" + rd_local()
        en = "_v_" + rd_local()

        tb = [
            ast.AugAssign(target=ast.Name(id=var_name), op=ast.Add(), value=ast.Constant(value=1)),
            ast.Try(
                body=[ast.Raise(exc=ast.Call(func=ast.Name(id='MemoryError'),
                                             args=[ast.Name(id=var_name)], keywords=[]))],
                handlers=[ast.ExceptHandler(type=ast.Name(id='MemoryError'), name=en, body=[])],
                orelse=[], finalbody=[]
            )
        ]
        for i in olb:
            tb[1].handlers[0].body.append(
                ast.If(
                    test=ast.Compare(
                        left=ast.Subscript(
                            value=ast.Attribute(value=ast.Name(id=en), attr='args'),
                            slice=ast.Constant(value=0)
                        ),
                        ops=[ast.Eq()],
                        comparators=[ast.Constant(value=1)]
                    ),
                    body=[i], orelse=[]
                )
            )
        tb[1].handlers[0].body.extend(junk(en, len(olb) + 1))
        node.body = [ast.Assign(targets=[ast.Name(id=var_name)], value=ast.Constant(value=0), lineno=None)] + tb
        return node

    def on(node):
        if isinstance(node, ast.FunctionDef):
            return _bl(node)
        return node

    nb = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nb.append(on(node))
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            nb.extend(bl([node]))
        elif isinstance(node, ast.Expr):
            nb.extend(bl([node]))
        elif isinstance(node, (ast.If, ast.While, ast.For)):
            nb.extend(bl([node]))
        else:
            nb.append(node)

    tree.body = nb
    return tree


def __moreobf(x):
    try:
        return ast.unparse(_moreobf(ast.parse(x)))
    except Exception as e:
        return x


# ═══════════════════════════════════════════════════════════════
# F-STRING HANDLER
# ═══════════════════════════════════════════════════════════════

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


def fm(node: ast.JoinedStr) -> ast.Call:
    template, args = _render_fstring_template(node)
    return ast.Call(
        func=ast.Attribute(
            value=ast.Constant(value=template),
            attr="format",
            ctx=ast.Load(),
        ),
        args=args,
        keywords=[],
    )


# ═══════════════════════════════════════════════════════════════
# SYNTAX OBFUSCATION
# ═══════════════════════════════════════════════════════════════

def _syntax(x):
    def v(node):
        if node.name:
            new_body = []
            for idx, statement in enumerate(node.body):
                if isinstance(statement, (ast.Global, ast.Nonlocal, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    new_body.append(statement)
                    continue
                # Skip docstring (first Expr containing Constant string)
                if idx == 0 and isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
                    new_body.append(statement)
                    continue
                ten = ast.Try(
                    body=[
                        ast.parse("0/0").body[0],
                        ast.parse(f"""if "ngocuyen" == "deptrai":{rd()},{rd()},{rd()},{rd()},{rd()}\nelse:pass""").body[0]
                    ],
                    handlers=[
                        ast.ExceptHandler(
                            type=ast.Name(id='ZeroDivisionError', ctx=ast.Load()),
                            name=None,
                            body=[z(statement)]
                        )
                    ],
                    orelse=[], finalbody=[]
                )
                new_body.append(ten)
            node.body = new_body
            return node

    def z(statement):
        return ast.Try(
            body=[ast.parse("0/0").body[0]],
            handlers=[
                ast.ExceptHandler(
                    type=ast.Name(id='ZeroDivisionError', ctx=ast.Load()),
                    name=None,
                    body=[statement]
                )
            ],
            orelse=[ast.Pass()],
            finalbody=[ast.parse("str(100)").body[0]]
        )

    tree = ast.parse(x)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            v(node)
    return ast.unparse(tree)


# ═══════════════════════════════════════════════════════════════
# CORE OBFUSCATION ENGINE
# ═══════════════════════════════════════════════════════════════

_obf_progress = {'current': 0, 'total': 0}

def _print_progress_bar(current, total, prefix='[TR0NGX]', suffix='identifiers obfuscated', length=40):
    """Animated progress bar display (disabled in quiet/CLI mode)."""
    if _cfg._EngineState.cli_quiet_mode:
        return
    import sys
    percent = float(current) * 100 / total if total > 0 else 0
    filled_length = int(length * current // total) if total > 0 else 0
    bar = '█' * filled_length + '░' * (length - filled_length)
    
    # Emoji theo progress
    if percent < 25:
        emoji = "🚀"
    elif percent < 50:
        emoji = "⚡"
    elif percent < 75:
        emoji = "🔥"
    elif percent < 90:
        emoji = "💎"
    else:
        emoji = "⭐"
    
    sys.stdout.write(f'\r{prefix}         {emoji} [{bar}] {percent:5.1f}% | {current}/{total} {suffix}')
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write('\n')
        sys.stdout.flush()

class _MainAstTransformer(ast.NodeTransformer):
    def __init__(self, skip_ids):
        self._skip_ids = skip_ids

    def visit_Constant(self, node: ast.Constant):
        if id(node) in self._skip_ids:
            return node
        # PERF: mode='eval' parses straight to the Expression node - skips the
        # Module+Expr wrapper the exec-mode parse built and threw away.
        if isinstance(node.value, bool):
            try:
                return ast.parse(obfint(node.value), mode='eval').body
            except Exception:
                return node
        elif isinstance(node.value, str):
            try:
                return ast.parse(obfstr(node.value), mode='eval').body
            except Exception:
                return node
        elif isinstance(node.value, int):
            try:
                return ast.parse(obfint(node.value), mode='eval').body
            except Exception:
                return node
        return node

    def visit_JoinedStr(self, node: ast.JoinedStr):
        try:
            return fm(node)
        except Exception:
            return node

def obfuscate(node):
    # Collect all AST node IDs that must NOT have constants replaced with lambda expressions
    _skip_ids = set()
    for n in ast.walk(node):
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

    transformer = _MainAstTransformer(_skip_ids)
    return transformer.visit(node)


def rename_function(node, ol, nn):

    if isinstance(node, str):
        node = ast.parse(node)
    # Scope safety: if the target name is locally bound (parameter, store target,
    # except-handler alias, import alias), renaming Loads would rebind user code
    # to the wrong object. Bail out of renaming for this pass.
    for i in ast.walk(node):
        if isinstance(i, ast.arg) and i.arg == ol:
            _diag._DEBUG_MAP["skipped_renames"].append(ol)
            return node
        if isinstance(i, ast.Name) and isinstance(i.ctx, (ast.Store, ast.Del)) and i.id == ol:
            _diag._DEBUG_MAP["skipped_renames"].append(ol)
            return node
        if isinstance(i, ast.ExceptHandler) and i.name == ol:
            _diag._DEBUG_MAP["skipped_renames"].append(ol)
            return node

    _diag._DEBUG_MAP["renamed_functions"][ol] = nn
    for i in ast.walk(node):
        if isinstance(i, ast.FunctionDef) and i.name == ol:
            i.name = nn
        elif isinstance(i, ast.AsyncFunctionDef) and i.name == ol:
            i.name = nn
        elif isinstance(i, ast.Attribute) and isinstance(i.value, ast.Name) and i.value.id == ol:
            i.value.id = nn
        elif isinstance(i, ast.Call) and isinstance(i.func, ast.Name) and i.func.id == ol:
            i.func.id = nn
        elif isinstance(i, ast.Name) and isinstance(i.ctx, ast.Load) and i.id == ol:
            i.id = nn
    return node


# ═══════════════════════════════════════════════════════════════
# MATCH-CASE JUNK GENERATOR
# ═══════════════════════════════════════════════════════════════

def random_match_case():
    val = randomint()
    var1 = ast.Constant(value=val, kind=None)
    var2 = ast.Constant(value=val, kind=None)

    junk_assigns = []
    for _ in range(random.randint(2, 5)):
        junk_assigns.append(
            ast.Assign(
                lineno=0, col_offset=0,
                targets=[ast.Name(id=rd(), ctx=ast.Store())],
                value=ast.Constant(value=random.randint(0, 0xFFFFFF), kind=None),
            )
        )

    return ast.Match(
        subject=ast.Compare(left=var1, ops=[ast.Eq()], comparators=[var2]),
        cases=[
            ast.match_case(
                pattern=ast.MatchValue(value=ast.Constant(value=True, kind=None)),
                body=[
                    ast.Raise(
                        exc=ast.Call(
                            func=ast.Name(id="MemoryError", ctx=ast.Load()),
                            args=[ast.Constant(value=True)],
                            keywords=[]
                        )
                    )
                ],
            ),
            ast.match_case(
                pattern=ast.MatchValue(value=ast.Constant(value=False, kind=None)),
                body=[
                    ast.Assign(
                        lineno=0, col_offset=0,
                        targets=[ast.Name(id=rd(), ctx=ast.Store())],
                        value=ast.Constant(value=[[True], [False], [None]], kind=None),
                    ),
                    ast.Expr(
                        lineno=0, col_offset=0,
                        value=ast.Call(
                            func=ast.Name(id=_str, ctx=ast.Load()),
                            args=[ast.Constant(value=[rd()], kind=None)],
                            keywords=[],
                        ),
                    ),
                ] + junk_assigns,
            ),
        ],
    )


def trycatch(body, loop=1):
    ar = []
    for x in body:
        if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Try)):
            ar.append(x)
            continue
        j = x
        for _ in range(loop):
            j = ast.Try(
                body=[random_match_case()],
                handlers=[
                    ast.ExceptHandler(
                        type=ast.Name(id="MemoryError", ctx=ast.Load()),
                        name=rd(), body=[j],
                    )
                ],
                orelse=[], finalbody=[],
            )
        ar.append(j)
    return ar


# ═══════════════════════════════════════════════════════════════
# MAIN OBFUSCATION PIPELINE
# ═══════════════════════════════════════════════════════════════

def obf(code, layer=1):
    def ps(x):
        if isinstance(x, str):
            return ast.parse(x)
        return x

    # Rename print/input once on layer 1
    if layer == 1:
        code = rename_function(ps(code), "print", __print)
        code = rename_function(code, "input", __input)

    tree = ps(code)
    obfuscate(tree)
    # Only inject match-case decoy try-except on layer 1 to prevent exponential bloat
    tbd = trycatch(tree.body, 1) if layer == 1 else tree.body

    def ast_to_code(node):
        if isinstance(node, list):
            return '\n'.join(ast.unparse(n) for n in node)
        return ast.unparse(node)

    return ast_to_code(tbd)



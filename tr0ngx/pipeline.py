# AUTO-SPLIT from tr0ngx_obfuscator.py (mechanical slice, imports pending repair)
import os
import sys
import time
import random
import marshal
import threading
import subprocess

from . import config as _cfg
from . import diagnostics as _diag
from . import names as _nm
from . import astpasses as _ap

from .diagnostics import (
    _v,
    _v_step,
    _log_stage_error,
    _track_debug_stage,
    _log_debug,
    _gradient_text,
    _export_log_file,
    _raw_print,
)
from .names import (
    rd,
    _collect_shared_symbol_map,
    _validate_input_source,
    _validate_and_sanitize_output_path,
    _safe_atomic_write,
    _gen_tr0ngx_header,
    _gen_zalgo_cascade_docstring,
    _gen_cjk_docstring,
    _gen_pycool_header,
)
from .velimatix import _velimatix_obf, OBF_Spam
from .astpasses import (
    ANTI_PYCDC,
    __moreobf,
    obf,
    obfstr,
    _syntax,
    _math_opaque_obf,
    _dyn_strings_obf,
    _dec_trap_obf,
    _var_split_obf,
    _str_frag_obf,
    _generate_anti_dump_shield,
    _generate_debug_poison_shield,
    _generate_spoof_meta_shield,
    _generate_var_block,
    _refresh_runtime_symbols,
)
from .shields import (
    anti,
    velimatix_anti_hook,
    _generate_self_modify_wrapper,
    _generate_anti_vm_shield,
)
from .crypto import _multi_layer_encrypt, _double_compile, _generate_strict_version_guard
from .vm import _vm_obfuscate
from .packagers import (
    _emoji_encode,
    _emoji_encode_v2,
    _whitespace_encode,
    _whitespace_encode_v2,
    _hyperion_camouflage,
    _hyperion_full_transform,
    _exotic_payload_wrap,
    _fused_matrix_wrap,
    _kramer_wrap,
)

def obfuscate_single_target(src_file: str, output_file: str, options: dict, quiet_progress: bool = False) -> dict:
    """
    Core transformation engine that executes the entire Tr0ngX pipeline on a single file.
    Returns metrics dict with status, file sizes, ratio, and timing.
    """
    with _nm._obf_execution_lock:
        # DIAG: start the RSS sampler so every stage reports a true in-stage peak.
        try:
            _diag._PEAK_RSS_SAMPLER.ensure_started()
        except Exception:
            pass
        # Per-target isolation: reset cross-file global state so batch debug maps,
        # used-name pools and stage errors never contaminate between files.
        _diag._DEBUG_MAP["stages"] = []
        _diag._DEBUG_MAP["errors"] = []
        _diag._DEBUG_MAP["renamed_functions"] = {}
        _diag._DEBUG_MAP["renamed_builtins"] = {}
        _diag._DEBUG_MAP["renamed_variables"] = {}
        _diag._DEBUG_MAP["skipped_renames"] = []
        while _diag._STAGE_ERRORS:
            _diag._STAGE_ERRORS.pop()
        with _nm._used_names_lock:
            _nm._used_names.clear()
        # Cross-module shared-symbol contract (--shared-symbols): install the
        # frozen map for this target while holding the pipeline lock.
        _nm._FROZEN_NAME_MAP.clear()
        _frozen = options.get("shared_symbol_map")
        if isinstance(_frozen, dict):
            _nm._FROZEN_NAME_MAP.update(_frozen)
        if options.get("seed") is not None:
            # Deterministic per-file seeding (independent of worker scheduling)
            _s_seed = options["seed"] + sum(src_file.encode("utf-8"))
            random.seed(_s_seed)
            _nm._SEEDED_RNG = random.Random(_s_seed ^ 0x5EED5EED)
            # Regenerate import-time helper names + global var-block template
            # under this file's seed so artifacts are reproducible (audit fix:
            # previously both baked OS entropy captured at module import).
            try:
                _refresh_runtime_symbols()
                _generate_var_block()
            except Exception:
                pass
        else:
            _nm._SEEDED_RNG = None
        return _obfuscate_single_target_core(src_file, output_file, options, quiet_progress=quiet_progress)
        return _obfuscate_single_target_core(src_file, output_file, options, quiet_progress=quiet_progress)

def _obfuscate_single_target_core(src_file: str, output_file: str, options: dict, quiet_progress: bool = False) -> dict:
    start_time = time.time()
    try:
        with open(src_file, "r", encoding="utf-8-sig", errors="replace") as f:
            code = f.read().lstrip('\ufeff')
        _validate_input_source(code)
        original_size = len(code.encode('utf-8'))
    except Exception as e:
        _log_stage_error("0_read_source_file", e)
        return {
            "success": False,
            "src": src_file,
            "out": output_file,
            "original_size": 0,
            "output_size": 0,
            "ratio": 0.0,
            "elapsed": round(time.time() - start_time, 4),
            "error": str(e)
        }

    mode = options["mode"]
    moreobf = options.get("moreobf", "N")
    antidebug = options.get("antidebug", "N")
    antivm = options.get("antivm", "N")
    selfmodify = options.get("selfmodify", "N")
    method = options.get("method", "N")
    encryption_password = options.get("password")
    custom_seed = options.get("seed")
    max_output_size = options.get("max_output_size")
    velimatix = options.get("velimatix", "N")
    veli_level = options.get("veli_level", 1)
    double_compile = options.get("double_compile", "N")
    kramer_wrap_choice = options.get("kramer", "N")
    cjk_choice = options.get("cjk", "N")
    matrix_choice = options.get("matrix", "N")
    emoji_obf_choice = options.get("emoji_obf", "N")
    homoglyph_choice = options.get("homoglyph", "N")
    rare_unicode_choice = options.get("rare_unicode", "N")
    zalgo_choice = options.get("zalgo", "N")
    whitespace_obf_choice = options.get("whitespace_obf", "N")
    blank_padding_choice = options.get("blank_padding", "N")
    hyperion_choice = options.get("hyperion", "N")
    camouflage_choice = options.get("camouflage", "N")
    math_opaque_choice = options.get("math_opaque", "N")
    dyn_strings_choice = options.get("dyn_strings", "N")
    antidump_choice = options.get("anti_dump", "N")
    vm_obf_choice = options.get("vm_obf", "N")
    vm_level_choice = options.get("vm_level", 1)
    dectrap_choice = options.get("dec_trap", "N")
    varsplit_choice = options.get("var_split", "N")
    strfrag_choice = options.get("str_frag", "N")
    debugpoison_choice = options.get("debug_poison", "N")
    spoofmeta_choice = options.get("spoof_meta", "N")
    exotic_pools_choice = options.get("exotic_pools", "N")
    base4096_choice = options.get("base4096", "N")
    bit_matrix_choice = options.get("bit_matrix", "N")
    _cfg._EngineState.lzma_layer = str(options.get("lzma_layer", "N")).upper() == "Y"
    _cfg._EngineState.env_key_lock = str(options.get("env_key", "N")).upper() == "Y" and not options.get("password")
    force_py_choice = options.get("force_py_choice", "N")
    forced_py_ver = options.get("forced_py_ver", "")
    _debug_map_choice = options.get("debug_map")

    # Step 0: Hyperion AST & Token Engine
    if hyperion_choice.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            if not quiet_progress: _v_step(0, 8, "Hyperion Token & AST Remapping Engine...")
            code = _hyperion_full_transform(code, camouflage=False, shell=False, randlines=False)
            _track_debug_stage("0_hyperion_engine", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("0_hyperion_engine", e)

    # Step 1: Syntax transform
    try:
        t0 = time.time()
        sz0 = len(code)
        if not quiet_progress: _v_step(1, 8, "Syntax transformation...")
        code = _syntax(code)
        _track_debug_stage("1_syntax_transform", time.time() - t0, sz0, len(code))
    except Exception as e:
        _log_stage_error("1_syntax_transform", e)

    # Step 2: AST junk injection
    if moreobf.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            if not quiet_progress: _v_step(2, 8, "AST junk injection...")
            code = __moreobf(code)
            _track_debug_stage("2_ast_junk_injection", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2_ast_junk_injection", e)

    # Step 2.3: Variable Secret Sharing (Var Split)
    if varsplit_choice.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            if not quiet_progress: _v_step("2.3", 8, "Integer Variable Secret Sharing (XOR Split)...")
            code = _var_split_obf(code, seed=custom_seed)
            _track_debug_stage("2.3_var_split_secret_sharing", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2.3_var_split_secret_sharing", e)

    # Step 2.4: Decompiler Trapping Matrix
    if dectrap_choice.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            if not quiet_progress: _v_step("2.4", 8, "Decompiler Control Flow Traps (uncompyle6/decompyle3/pycdc breaker)...")
            code = _dec_trap_obf(code, density=0.6, seed=custom_seed)
            _track_debug_stage("2.4_decompiler_traps", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2.4_decompiler_traps", e)

    # Step 2.5: Mathematical Opaque Predicates
    if math_opaque_choice.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            if not quiet_progress: _v_step("2.5", 8, "Mathematical Opaque Predicates (Quadratic Non-Residue mod 7 & Euler invariants)...")
            code = _math_opaque_obf(code)
            _track_debug_stage("2.5_math_opaque_predicates", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2.5_math_opaque_predicates", e)

    # Step 2.7: Dynamic Per-Callsite String XOR
    if dyn_strings_choice.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            if not quiet_progress: _v_step("2.7", 8, "Dynamic Per-Callsite String XOR Encryption...")
            code = _dyn_strings_obf(code, seed=custom_seed)
            _track_debug_stage("2.7_dyn_strings_encryption", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2.7_dyn_strings_encryption", e)

    # Step 2.8: String Fragmentation & Decoy Pool
    if strfrag_choice.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            if not quiet_progress: _v_step("2.8", 8, "String Fragmentation & Decoy Pool (strfrag2)...")
            code = _str_frag_obf(code, seed=custom_seed)
            _track_debug_stage("2.8_str_frag_pool", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2.8_str_frag_pool", e)

    # Step 3: Version check header
    target_ver_str = forced_py_ver if (force_py_choice.upper() == "Y" and forced_py_ver) else f"{sys.version_info.major}.{sys.version_info.minor}"
    checkver = _generate_strict_version_guard(target_ver_str)

    if cjk_choice.upper() == "Y":
        pycool_hdr = _gen_pycool_header()
        author = pycool_hdr + f"""((
    ((([["TR0NGX x VELIMATIX x PYCOOL MAXIMUM POWER"],
    ["https://github.com/Tr0ngX"],
    ["PYTHON AST OBFUSCATOR v4.0 - PYCOOL CJK EDITION"],
    3.11
    ],
    [__import__("builtins").exec(
    {checkver.encode()})
    ])
    )
    )
    )
)
"""
    else:
        author = f"""((
    ((([["TR0NGX x VELIMATIX MAXIMUM POWER"],
    ["https://github.com/Tr0ngX"],
    ["PYTHON AST OBFUSCATOR v4.0"],
    3.11
    ],
    [__import__("builtins").exec(
    {checkver.encode()})
    ])
    )
    )
    )
)
"""

    # Step 4: Velimatix Engine
    if velimatix.upper() == "Y":
        if not quiet_progress: _v_step(3, 8, f"Velimatix engine (level {veli_level})...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _velimatix_obf(code, mode=veli_level)
            _track_debug_stage(f"3_velimatix_level_{veli_level}", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error(f"3_velimatix_level_{veli_level}", e)

    # Step 5: Main Obfuscation Layers
    if not quiet_progress: _v_step(4, 8, f"Applying {mode}-layer tr0ngx obfuscation...")
    for i in range(mode):
        try:
            t0 = time.time()
            sz0 = len(code)
            new_code = obf(code, layer=i + 1)
            code = new_code
            _track_debug_stage(f"4_tr0ngx_layer_{i+1}_of_{mode}", time.time() - t0, sz0, len(code))
            if not quiet_progress: _v(f"        - Layer {i + 1}/{mode} complete")
        except Exception as e:
            _log_stage_error(f"4_tr0ngx_layer_{i+1}_of_{mode}", e)
            break

    # Step 6: Anti-Debug, Anti-VM, Anti-Dump, Self-Mod
    if antidebug.upper() == "Y":
        if not quiet_progress: _v_step(5, 8, "Injecting anti-debug shield...")
        t0 = time.time()
        sz0 = len(code)
        if velimatix.upper() == "Y":
            code = velimatix_anti_hook + code
        code = anti + code
        _track_debug_stage("5_anti_debug_injection", time.time() - t0, sz0, len(code))

    if antivm.upper() == "Y":
        if not quiet_progress: _v_step("5.2", 8, "Injecting Anti-VM & Sandbox shield...")
        t0 = time.time()
        sz0 = len(code)
        code = _generate_anti_vm_shield() + code
        _track_debug_stage("5.2_anti_vm_injection", time.time() - t0, sz0, len(code))

    if antidump_choice.upper() == "Y":
        if not quiet_progress: _v_step("5.4", 8, "Injecting In-Memory Anti-Dump & GC Scrubber shield...")
        t0 = time.time()
        sz0 = len(code)
        code = _generate_anti_dump_shield() + code
        _track_debug_stage("5.4_anti_dump_shield", time.time() - t0, sz0, len(code))

    if selfmodify.upper() == "Y":
        if not quiet_progress: _v_step("5.5", 8, "Adding self-modifying layer...")
        t0 = time.time()
        sz0 = len(code)
        code = _generate_self_modify_wrapper() + code
        _track_debug_stage("5.5_self_modify_layer", time.time() - t0, sz0, len(code))

    if debugpoison_choice.upper() == "Y":
        if not quiet_progress: _v_step("5.6", 8, "Injecting Deceptive Debug Poison State Machine...")
        t0 = time.time()
        sz0 = len(code)
        code = _generate_debug_poison_shield() + code
        _track_debug_stage("5.6_debug_poison_shield", time.time() - t0, sz0, len(code))

    # Step 6.5: VM Virtualization Engine
    if vm_obf_choice.upper() == "Y":
        if not quiet_progress: _v_step("6.5", 8, f"VM Virtualization Engine (level {vm_level_choice})...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _vm_obfuscate(code, seed=custom_seed, vm_level=int(vm_level_choice))
            _track_debug_stage("6.5_optimization_pass", time.time() - t0, sz0, len(code), details={"tier": vm_level_choice})
        except Exception as e:
            _log_stage_error("6.5_optimization_pass", e)

    # Step 8: Packaging & Compilation
    # Snapshot the rebindable astpasses globals (regenerated by
    # _refresh_runtime_symbols/_generate_var_block under --seed) so the
    # loader f-strings below always interpolate the current-build values.
    _var_template = _ap.var
    _ap___import__name = _ap.___import__
    if method.upper() != "Y":
        if not quiet_progress: _v_step(6, 8, "Building non-compiled output...")
        t0 = time.time()
        sz0 = len(code)
        code = author + _var_template + code
        if moreobf.upper() == "Y":
            try: code = __moreobf(code)
            except Exception: pass
        if velimatix.upper() == "Y" and veli_level >= 2:
            try: code = OBF_Spam(code, level=min(veli_level, 2))
            except Exception: pass
        _track_debug_stage("6_non_compiled_packaging", time.time() - t0, sz0, len(code))
    else:
        if not quiet_progress: _v_step(6, 8, "Multi-layer compilation...")
        t0 = time.time()
        sz0 = len(code)
        if moreobf.upper() == "Y":
            try: code = __moreobf(code)
            except Exception: pass
        code = ANTI_PYCDC + code

        if double_compile.upper() == "Y":
            if not quiet_progress: _v_step(7, 8, "DOUBLE COMPILE (Tr0ngX + Velimatix)...")
            try:
                code = _double_compile(_var_template + code, target_ver=target_ver_str, password=encryption_password)
                _track_debug_stage("7_double_compile_packaging", time.time() - t0, sz0, len(code))
            except Exception as e:
                _log_stage_error("7_double_compile_packaging", e)
                double_compile = "N"

        if double_compile.upper() != "Y":
            try:
                compiled_bytes = marshal.dumps(compile(code, "<tr0ngx>", "exec"))
            except SyntaxError as e:
                _log_stage_error("7_compile_syntax_error", e)
                code = _var_template + code
                _safe_atomic_write(output_file, str(code), input_file=src_file)
                return {"success": True, "src": src_file, "out": output_file, "original_size": original_size, "output_size": len(code.encode('utf-8')), "ratio": 1.0, "elapsed": round(time.time()-start_time, 4), "error": None}

            encrypted_data, _salt, _armor = _multi_layer_encrypt(compiled_bytes, password=encryption_password)
            _armor_dec = _armor['dec']
            _armor_rev = "[::-1]" if _armor['rev'] else ""
            if _armor['lzma']:
                _lzma_import = ", lzma"
                _lzma_var = rd()
                _lzma_extra = f"{_lzma_var} = getattr({_ap___import__name}({obfstr('lzma')}), {obfstr('decompress')})" + chr(10) + f"    _step5 = {_lzma_var}(_step5)"
            else:
                _lzma_import = ""
                _lzma_extra = ""
            if _cfg._EngineState.env_key_lock and not encryption_password:
                _envkey_unmask_std = chr(10).join([
                    "    try:",
                    "        import uuid as _trx_u",
                    "        _trx_fp = hashlib.sha256(('|'.join([str(_trx_u.getnode()), _platform.system(), _platform.machine(), _platform.python_implementation(), str(sys.version_info.major) + '.' + str(sys.version_info.minor)])).encode()).digest()",
                    "        salt = bytes(salt[i] ^ _trx_fp[i] for i in range(16))",
                    "    except Exception:",
                    "        raise SystemExit(1)",
                ])
            else:
                _envkey_unmask_std = "# portable build: no hardware binding"
            l = len(encrypted_data)
            num_parts = 8
            parts = [repr(encrypted_data[(l*k)//num_parts : (l*(k+1))//num_parts]) for k in range(num_parts)]
            part_vars = [rd() for _ in range(num_parts)]
            part_assignments = '\n'.join(f"{part_vars[k]}  {'  '*500}={parts[k]}" for k in range(num_parts))
            part_concat = '+'.join(part_vars)

            _en_var, _july_var, _birth_var, _b85_var = rd(), rd(), rd(), rd()
            if encryption_password:
                _auth_dec_section = f"""
def _derive_key(password_bytes, salt):
    try:
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
        return Argon2id(salt=salt + b'__enc__', length=32, iterations=3, lanes=2, memory_cost=65536).derive(password_bytes)
    except ImportError:
        return hashlib.pbkdf2_hmac('sha256', password_bytes, salt + b'__enc__', 600000, 32)

def _auth_decrypt(raw_bytes, pwd_str):
    magic = raw_bytes[:4]
    salt = raw_bytes[4:20]
    p_bytes = pwd_str.encode('utf-8')
    ke = _derive_key(p_bytes, salt)
    body = raw_bytes[20:]
    if magic == b'TRXA':
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        nonce = body[:12]
        ct = body[12:]
        try:
            return ChaCha20Poly1305(ke).decrypt(nonce, ct, salt)
        except Exception:
            print("[-] Authentication / Decryption Failed: Invalid password or tampered payload.", flush=True)
            sys.exit(1)
    elif magic == b'TRXH':
        nonce = body[:12]
        tag = body[12:44]
        ct = body[44:]
        km_eff = hashlib.sha256(ke + b'__mac__').digest()
        expected_tag = hmac.new(km_eff, salt + nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            print("[-] Authentication / Decryption Failed: Invalid password or tampered payload.", flush=True)
            sys.exit(1)
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(ct):
            block = hmac.new(ke, nonce + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1
        return bytes(a ^ b for a, b in zip(ct, keystream[:len(ct)]))
    print("[-] Unknown payload format.", flush=True)
    sys.exit(1)

_pwd = __import__("os").environ.get("TR0NGX_PASSWORD")
if not _pwd:
    import getpass as _gp
    _pwd = _gp.getpass("[TR0NGX] Enter decryption password: ")
"""
                _auth_dec_call = "_auth_decrypt(_step3, _pwd)"
            else:
                _auth_dec_section = f"""
def _derive_runtime_keys(salt):
    _parts = []
    _parts.append(sys.version[:5].encode())
    _parts.append(_platform.python_implementation().encode())
    _parts.append(salt)
    _parts.append(str(sys.maxsize).encode())
    _parts.append(sys.byteorder.encode())
    _combined = b''.join(_parts)
    _enc_k = hashlib.sha256(_combined + b'__enc__').digest()
    return _enc_k

def _auth_decrypt(raw_bytes):
    magic = raw_bytes[:4]
    salt = raw_bytes[4:20]
{_envkey_unmask_std}
    _enc_k = _derive_runtime_keys(salt)
    ke = hashlib.pbkdf2_hmac('sha256', salt, _enc_k, 50000, 32)
    body = raw_bytes[20:]
    if magic == b'TRXA':
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        nonce = body[:12]
        ct = body[12:]
        return ChaCha20Poly1305(ke).decrypt(nonce, ct, salt)
    elif magic == b'TRXH':
        nonce = body[:12]
        tag = body[12:44]
        ct = body[44:]
        km_eff = hashlib.sha256(ke + b'__mac__').digest()
        expected_tag = hmac.new(km_eff, salt + nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise SystemExit(1)
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(ct):
            block = hmac.new(ke, nonce + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1
        return bytes(a ^ b for a, b in zip(ct, keystream[:len(ct)]))
    raise SystemExit(1)
"""
                _auth_dec_call = "_auth_decrypt(_step3)"

            code = author + _var_template + f"""
import hashlib, hmac, platform as _platform, sys, os{_lzma_import}
sys.dont_write_bytecode = True
{_generate_strict_version_guard(target_ver_str)}

{_auth_dec_section}

{_en_var} = getattr({_ap___import__name}({obfstr("marshal")}), {obfstr("loads")})
{_july_var} = getattr({_ap___import__name}({obfstr("zlib")}), {obfstr("decompress")})
{_birth_var} = getattr({_ap___import__name}({obfstr("bz2")}), {obfstr("decompress")})
{_b85_var} = getattr({_ap___import__name}({obfstr("base64")}), {obfstr(_armor_dec)})

{part_assignments}

try:
    _payload = {part_concat}
    _step1 = {_b85_var}(_payload{_armor_rev})
    _step2 = {_july_var}(_step1)
    _step3 = {_birth_var}(_step2)
    _step4 = {_auth_dec_call}
    _step5 = {_july_var}(_step4)
    {_lzma_extra}
    exec({_en_var}(_step5), globals(), globals())
    del _payload, _step1, _step2, _step3, _step4, _step5
except Exception as _e:
    raise _e
"""
            if velimatix.upper() == "Y" and veli_level >= 2:
                try: code = OBF_Spam(code, level=1)
                except Exception: pass
            _track_debug_stage("7_standard_compile_packaging", time.time() - t0, sz0, len(code))

    # Outer Shield Matrix & Camouflage
    multi_shield_count = sum(1 for c in [kramer_wrap_choice, emoji_obf_choice, whitespace_obf_choice] if c.upper() == "Y")
    is_fused_shield = (matrix_choice.upper() == "Y") or (multi_shield_count >= 2)

    if camouflage_choice.upper() == "Y":
        if not quiet_progress: _v(" [12] Applying Hyperion Scientific Class Camouflage...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _hyperion_camouflage(code)
            _track_debug_stage("12_hyperion_camouflage", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("12_hyperion_camouflage", e)

    if bit_matrix_choice.upper() == "Y" or base4096_choice.upper() == "Y":
        if not quiet_progress: _v(" [11.5] Applying Exotic Byte/Glyph Encoding (BitMatrix + Base4096)...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _exotic_payload_wrap(code, use_bitmatrix=(bit_matrix_choice.upper() == "Y"), use_base4096=(base4096_choice.upper() == "Y"))
            _track_debug_stage("11.5_exotic_payload_wrap", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("11.5_exotic_payload_wrap", e)

    if is_fused_shield:
        if not quiet_progress: _v(" [9/9] Applying Fused Matrix Shield (Kyrie + Emoji + Whitespace Symbiotic)...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _fused_matrix_wrap(code, already_packaged=(double_compile.upper() == "Y"))
            _track_debug_stage("8_fused_matrix_shield", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("8_fused_matrix_shield", e)
    else:
        if kramer_wrap_choice.upper() == "Y":
            if not quiet_progress: _v(" [9/9] Applying Kramer Outer Shield (Kyrie Eleison)...")
            try:
                t0 = time.time()
                sz0 = len(code)
                code = _kramer_wrap(code)
                _track_debug_stage("8_kramer_outer_shield", time.time() - t0, sz0, len(code))
            except Exception as e:
                _log_stage_error("8_kramer_outer_shield", e)

        if emoji_obf_choice.upper() == "Y":
            try:
                t0 = time.time()
                sz0 = len(code)
                code = _emoji_encode_v2(code, already_packaged=(double_compile.upper() == "Y")) if method.upper() == "Y" else _emoji_encode(code)
                _track_debug_stage("9_emoji_obfuscation", time.time() - t0, sz0, len(code))
            except Exception as e:
                _log_stage_error("9_emoji_obfuscation", e)

        if whitespace_obf_choice.upper() == "Y":
            try:
                t0 = time.time()
                sz0 = len(code)
                code = _whitespace_encode_v2(code, already_packaged=(double_compile.upper() == "Y")) if method.upper() == "Y" else _whitespace_encode(code)
                _track_debug_stage("10_whitespace_obfuscation", time.time() - t0, sz0, len(code))
            except Exception as e:
                _log_stage_error("10_whitespace_obfuscation", e)

    if spoofmeta_choice.upper() == "Y":
        if not quiet_progress: _v(" [12.5] Injecting Metadata Spoofing & Signature Debranding...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _generate_spoof_meta_shield() + code
            _track_debug_stage("12.5_spoof_meta_shield", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("12.5_spoof_meta_shield", e)

    _blank_pad = ("\n" * 300) if blank_padding_choice.upper() == "Y" else ""
    if zalgo_choice.upper() == "Y":
        code = _gen_tr0ngx_header() + "\n" + _blank_pad + _gen_zalgo_cascade_docstring(paragraphs=1, lines_per_p=6, chars_per_line=12, marks_per_char=50) + "\n" + code + "\n" + _gen_zalgo_cascade_docstring(paragraphs=1, lines_per_p=4, chars_per_line=12, marks_per_char=50)
    elif cjk_choice.upper() == "Y" or matrix_choice.upper() == "Y" or rare_unicode_choice.upper() == "Y":
        code = _gen_tr0ngx_header() + "\n" + _blank_pad + _gen_cjk_docstring(paragraphs=1, lines_per_p=5, chars_per_line=36) + "\n" + code + "\n" + _gen_cjk_docstring(paragraphs=1, lines_per_p=4, chars_per_line=36)
    else:
        code = _gen_tr0ngx_header() + "\n" + _blank_pad + code

    # Write output atomically
    _safe_atomic_write(output_file, str(code), input_file=src_file)
    elapsed = time.time() - start_time
    file_size = os.path.getsize(output_file)
    ratio = file_size / original_size if original_size > 0 else 0

    if max_output_size and file_size > max_output_size:
        if os.path.isfile(output_file):
            try: os.remove(output_file)
            except Exception: pass
        raise ValueError(f"Output size ({file_size:,} B) exceeded limit ({max_output_size:,} B)")

    if _debug_map_choice is not None:
        dbg_map_file = (os.path.splitext(output_file)[0] + ".debug.json") if _debug_map_choice == "AUTO" else _debug_map_choice
        try:
            import json
            dbg_map_file = _validate_and_sanitize_output_path(dbg_map_file, input_file=src_file)
            _safe_atomic_write(dbg_map_file, json.dumps(_diag._DEBUG_MAP, indent=2, ensure_ascii=False), input_file=src_file)
        except Exception as de:
            _log_stage_error("debug_map_export", de)

    # Built-in semantic verification (--verify y)
    if _cfg._EngineState.verify_mode:
        if not quiet_progress: _v(" [VERIFY] Semantic differential: original vs obfuscated...")
        t_v0 = time.time()
        vres = _verify_semantics(src_file, output_file)
        try:
            _track_debug_stage("13_verify_semantic", time.time() - t_v0, original_size, file_size, details=vres)
        except Exception:
            pass
        if not vres.get('ok'):
            try:
                _log_stage_error("13_verify_semantic", RuntimeError("obfuscated output diverged from original"), {"result": vres})
            except Exception:
                pass
            print("[TR0NGX] [WARNING] VERIFY FAILED: obfuscated output differs from original.", flush=True)

    return {
        "success": True,
        "src": src_file,
        "out": output_file,
        "original_size": original_size,
        "output_size": file_size,
        "ratio": ratio,
        "elapsed": round(elapsed, 4),
        "error": None
    }

def _verify_semantics(src_file: str, out_file: str, timeout: int = 60) -> dict:
    """Built-in semantic differential check (source: pyshield --verify mode, MIT
    research note; hardened to compare exit codes in addition to stdout)."""
    try:
        r1 = subprocess.run([sys.executable, src_file], capture_output=True, timeout=timeout)
        r2 = subprocess.run([sys.executable, out_file], capture_output=True, timeout=timeout)
        ok = (r1.stdout.strip() == r2.stdout.strip()) and (r1.returncode == r2.returncode)
        return {'ok': ok, 'rc_original': r1.returncode, 'rc_obfuscated': r2.returncode,
                'stdout_match': r1.stdout.strip() == r2.stdout.strip()}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def run_batch_obfuscation(targets: list, custom_out: str, options: dict):
    """
    Executes multi-threaded parallel batch obfuscation for multiple target files.
    """
    start_batch = time.time()
    total_files = len(targets)
    workers = options.get("workers") or max(2, min(8, os.cpu_count() or 4))
    
    # Destination directory resolution
    if custom_out:
        out_dir = custom_out.strip().strip('"').strip("'")
    else:
        first_dir = os.path.dirname(targets[0]["src"]) or "."
        out_dir = os.path.join(first_dir, "tr0ngx_dist")
    
    os.makedirs(out_dir, exist_ok=True)

    # Phase A: cross-module shared-symbol map (--shared-symbols y). Single-threaded
    # parse of all targets BEFORE any worker starts; workers consume the frozen
    # immutable map (Opy consistency model, hardened two-phase design).
    if str(options.get("shared_symbols", "N")).upper() == "Y" and len(targets) > 1:
        try:
            options["shared_symbol_map"] = _collect_shared_symbol_map(targets, seed=options.get("seed"))
            _v(f"  [SHARED-SYMBOLS] Frozen {len(options['shared_symbol_map'])} cross-module symbol(s)")
            try:
                import json as _json
                _safe_atomic_write(os.path.join(out_dir, "tr0ngx_shared_symbols.json"),
                                   _json.dumps(options["shared_symbol_map"], indent=2))
            except Exception:
                pass
        except Exception as _ss_err:
            _log_stage_error("shared_symbols_phase_a", _ss_err)
            options["shared_symbol_map"] = {}
    else:
        options.pop("shared_symbol_map", None)

    _v(_gradient_text(" ══════════════════════════════════════════════════════════════════════════════", (80, 180, 255), (200, 80, 255)))
    _v(f"  [TR0NGX BATCH ENGINE] Starting parallel batch obfuscation ({total_files} files, {workers} workers)")
    _v(f"  Destination Dir : {os.path.abspath(out_dir)}")
    _v(_gradient_text(" ══════════════════════════════════════════════════════════════════════════════", (80, 180, 255), (200, 80, 255)))

    results = []
    completed_lock = threading.Lock()
    completed_count = 0

    def _worker_task(t_info):
        nonlocal completed_count
        src = t_info["src"]
        rel = t_info["rel"]
        dest = os.path.join(out_dir, rel)
        dest_dir = os.path.dirname(dest)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)

        res = obfuscate_single_target(src, dest, options, quiet_progress=True)
        with completed_lock:
            completed_count += 1
            cur = completed_count
        
        status_tag = "\033[92m[OK]\033[0m" if res["success"] else "\033[91m[FAIL]\033[0m"
        rel_display = rel if len(rel) <= 35 else ("..." + rel[-32:])
        if res["success"]:
            _v(f"  [{cur:>{len(str(total_files))}}/{total_files}] {status_tag} {rel_display:<35} -> {res['output_size']:>10,} B ({res['ratio']:>5.1f}x | {res['elapsed']:>5.2f}s)")
        else:
            _v(f"  [{cur:>{len(str(total_files))}}/{total_files}] {status_tag} {rel_display:<35} -> ERROR: {res['error']}")
        return res

    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=min(workers, total_files)) as executor:
        futures = [executor.submit(_worker_task, t) for t in targets]
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except SystemExit:
                raise
            except KeyboardInterrupt:
                raise
            except Exception as e:
                _log_debug(f"Worker crashed: {e}", level="ERROR")
                import traceback as _tb2
                _log_debug(_tb2.format_exc(), level="ERROR")
                results.append({"success": False, "src": "?", "out": "?", "original_size": 0, "output_size": 0, "ratio": 0.0, "elapsed": 0.0, "error": str(e)})

    total_batch_time = time.time() - start_batch
    success_count = sum(1 for r in results if r["success"])
    fail_count = total_files - success_count
    total_in_bytes = sum(r["original_size"] for r in results)
    total_out_bytes = sum(r["output_size"] for r in results if r["success"])
    overall_ratio = (total_out_bytes / total_in_bytes) if total_in_bytes > 0 else 0

    summary_lines = [
        f"Total Files Processed : {total_files}",
        f"Successful            : {success_count} / {total_files} ({success_count/total_files*100:.1f}%)",
        f"Failed                : {fail_count}",
        f"Total Original Size   : {total_in_bytes:,} bytes",
        f"Total Obfuscated Size : {total_out_bytes:,} bytes ({overall_ratio:.1f}x expansion)",
        f"Total Elapsed Time    : {total_batch_time:.2f}s (Avg: {total_batch_time/total_files:.2f}s/file)",
        f"Output Destination    : {os.path.abspath(out_dir)}"
    ]
    summary_text = "\n".join(summary_lines)

    _v(_gradient_text(" ══════════════════════ BATCH OBFUSCATION SUMMARY ══════════════════════", (85, 130, 255), (190, 85, 255)))
    if _cfg._EngineState.cli_quiet_mode:
        _v(summary_text)
    else:
        try:
            _boxed = _cfg.Box.DoubleCube(summary_text)
            _raw_print(_cfg.Colorate.Diagonal(_cfg.Colors.StaticMIX((_cfg.Col.cyan, _cfg.Col.purple)), _boxed))
        except Exception:
            _v(summary_text)
    _v(_gradient_text(" ═══════════════════════════════════════════════════════════════════════", (85, 130, 255), (190, 85, 255)))
    _export_log_file()
    _v(" BATCH OBFUSCATION COMPLETE!")
    if fail_count > 0:
        sys.exit(1)
    return results

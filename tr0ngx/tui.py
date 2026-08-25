# Interactive TUI layer (extracted from the original monolith dispatcher).
# ═══════════════════════════════════════════════════════════════
# Hosts the no-CLI-args interactive flows: file/batch selection menu,
# protection profile presets, and the step-by-step option prompts.
# Prompt ORDER and semantics are unchanged from the original; rendering is
# the only thing that moved (gradient panels, aligned menus, clear states).
# All user-facing text is English.

# stdlib wiring
import os
import sys
import ast

# pure UI/diagnostic helpers
from .diagnostics import (
    _v,
    _gradient_text,
    _prompt_input,
)

# color primitives (pystyle-backed with safe fallbacks)
from .config import Col, Colors, Colorate

# input source security validation
from .names import _validate_input_source

# Static edge toward cli: the batch file-selection loop reuses
# _resolve_input_files, which stays owned by cli.py next to the argparse
# path. Safe because cli.py only imports this module lazily at call time,
# so the package graph stays acyclic.
from .cli import _resolve_input_files

# ── visual language ──────────────────────────────────────────────
# One accent ramp used everywhere: cyan → violet. Box drawing via plain
# characters so it renders on every Windows terminal without font tricks.
_C1 = (0, 240, 255)
_C2 = (140, 80, 255)
_W = 74


def _g(text: str) -> str:
    return _gradient_text(text, _C1, _C2)


def _rule(label: str = "") -> None:
    """Section divider: ──── LABEL ────"""
    if label:
        pad = max(0, _W - len(label) - 8)
        _v(_g("  ─" * 3 + f"  {label}  " + "─" * pad))
    else:
        _v(_g("  " + "─" * _W))


def _panel(title: str, subtitle: str = "") -> None:
    """Big gradient header panel."""
    inner = _W - 2
    top = "╔" + "═" * inner + "╗"
    bot = "╚" + "═" * inner + "╝"
    t_pad = max(0, (inner - len(title)) // 2)
    s_pad = max(0, (inner - len(subtitle)) // 2)
    row_t = "║" + " " * t_pad + title + " " * (inner - t_pad - len(title)) + "║"
    row_s = "║" + " " * s_pad + subtitle + " " * (inner - s_pad - len(subtitle)) + "║"
    blank = "║" + " " * inner + "║"
    _v(_g("  " + top))
    _v("  " + Col.white + row_t)
    if subtitle:
        _v(Col.dark_gray + "  " + row_s)
    _v("  " + blank)
    _v(_g("  " + bot))


def _option(num: str, label: str, desc: str) -> None:
    """Aligned menu row:  [1] LABEL      · description"""
    col = 26
    lbl = f"  [{num}] "
    pad = max(1, col - len(lbl))
    line = lbl + Col.white + label.ljust(pad - 1) + Col.dark_gray + "· " + desc
    _v(line)


def _ok(msg: str) -> None:
    _v(Col.green + f"  [+] {msg}" + Col.reset)


def _warn(msg: str) -> None:
    _v(Col.yellow + f"  [!] {msg}" + Col.reset)


def _err(msg: str) -> None:
    _v(Col.red + f"  [-] {msg}" + Col.reset)


def run_interactive(cli_args):
    """Interactive entry: file/batch selection menu + protection profile menu.

    Returns (targets, is_batch, custom_out, _setup).
    """
    targets = []
    is_batch = False
    custom_out = cli_args.output

    _panel(
        "TR0NGX ULTIMATE AST OBFUSCATOR",
        "interactive setup · python code protection suite v4.0",
    )
    _rule("INPUT MODE")
    _option(1, "SINGLE FILE", "protect one .py script")
    _option(2, "BATCH / DIRECTORY", "many files, glob patterns or a whole tree")
    file_mode_choice = _prompt_input(" Choose (1/2, default 1): ").strip()
    if file_mode_choice == "2":
        is_batch = True
        while True:
            batch_inp = _prompt_input(" Directory / glob / files (e.g. src/, *.py): ").strip().strip('"').strip("'")
            rec_inp = _prompt_input(" Recurse subdirectories? (y/n, default n): ").strip().upper()
            is_rec = (rec_inp == "Y")
            try:
                targets = _resolve_input_files(inputs=batch_inp, directory=batch_inp if os.path.isdir(batch_inp) else None, recursive=is_rec)
                if targets:
                    _ok(f"found {len(targets)} Python files for batch obfuscation")
                    for t_idx, t in enumerate(targets[:10], 1):
                        _v(Col.light_gray + f"       {t_idx:>2}. {t['rel']}" + Col.reset)
                    if len(targets) > 10:
                        _v(Col.dark_gray + f"       ... and {len(targets) - 10} more." + Col.reset)
                    break
                else:
                    _warn("no matching .py files found - try again")
            except Exception as e:
                _err(f"file discovery failed: {e} - try again")

        out_dir_inp = _prompt_input(" Output directory (default tr0ngx_dist/): ").strip().strip('"').strip("'")
        custom_out = out_dir_inp if out_dir_inp else "tr0ngx_dist"
    else:
        _file = _prompt_input(" Enter file path: ").strip().strip('"').strip("'")
        while True:
            try:
                if not os.path.isfile(_file):
                    raise FileNotFoundError(f"File not found: {_file}")
                with open(_file, "r", encoding="utf-8-sig", errors="replace") as file:
                    raw_code = file.read().lstrip('\ufeff')
                _validate_input_source(raw_code)
                ast.parse(raw_code)
                targets = [{"src": os.path.abspath(_file), "rel": os.path.basename(_file)}]
                _ok(f"loaded {_file}")
                break
            except Exception as e:
                _err(f"syntax/security check failed: {e}")
                _file = _prompt_input(" Enter file path again: ").strip().strip('"').strip("'")

    _panel(
        "PROTECTION PROFILE",
        "pick a preset now or fine-tune all 17 layers step by step",
    )
    _option(1, "FAST", "mode 1 AST pass + dynamic strings · builds in seconds")
    _option(2, "BALANCED", "mode 2 + AEAD compile + Velimatix L2 + fused matrix")
    _option(3, "MAXIMUM ARSENAL", "mode 3 + TVM L3 + camouflage + zalgo + traps + poison")
    _v(Col.dark_gray + "                              + anti-dump + spoof meta" + Col.reset)
    _option(4, "CUSTOM STEP-BY-STEP", "hand-tune every protection layer")

    _setup = _prompt_input(" Choose profile (1/2/3/4, default 2): ").strip()
    if not _setup:
        _setup = "2"

    if _setup == "1":
        cli_args.mode = 1
        cli_args.moreobf = "N"
        cli_args.antidebug = "N"
        cli_args.antivm = "N"
        cli_args.selfmod = "N"
        cli_args.compile = "N"
        cli_args.velimatix = "N"
        cli_args.veli_level = 1
        cli_args.double_compile = "N"
        cli_args.kramer = "N"
        cli_args.cjk_vars = "N"
        cli_args.matrix = "N"
        cli_args.emoji_obf = "N"
        cli_args.homoglyph = "N"
        cli_args.rare_unicode = "N"
        cli_args.zalgo = "N"
        cli_args.whitespace_obf = "N"
        cli_args.blank_padding = "N"
        cli_args.hyperion = "N"
        cli_args.camouflage = "N"
        cli_args.math_opaque = "N"
        cli_args.dyn_strings = "Y"
        cli_args.anti_dump = "N"
        cli_args.vm_obf = "N"
        cli_args.vm_level = 1
        cli_args.dec_trap = "N"
        cli_args.var_split = "N"
        cli_args.str_frag = "N"
        cli_args.debug_poison = "N"
        cli_args.spoof_meta = "N"
        cli_args.force_py = "off"
    elif _setup == "2":
        cli_args.mode = 2
        cli_args.moreobf = "Y"
        cli_args.antidebug = "Y"
        cli_args.antivm = "Y"
        cli_args.selfmod = "N"
        cli_args.compile = "Y"
        cli_args.velimatix = "Y"
        cli_args.veli_level = 2
        cli_args.double_compile = "Y"
        cli_args.kramer = "N"
        cli_args.cjk_vars = "N"
        cli_args.matrix = "Y"
        cli_args.emoji_obf = "N"
        cli_args.homoglyph = "N"
        cli_args.rare_unicode = "N"
        cli_args.zalgo = "N"
        cli_args.whitespace_obf = "N"
        cli_args.blank_padding = "N"
        cli_args.hyperion = "N"
        cli_args.camouflage = "N"
        cli_args.math_opaque = "Y"
        cli_args.dyn_strings = "Y"
        cli_args.anti_dump = "Y"
        cli_args.vm_obf = "N"
        cli_args.vm_level = 1
        cli_args.dec_trap = "Y"
        cli_args.var_split = "Y"
        cli_args.str_frag = "Y"
        cli_args.debug_poison = "Y"
        cli_args.spoof_meta = "Y"
        cli_args.force_py = "off"
    elif _setup == "3":
        cli_args.mode = 3
        cli_args.moreobf = "Y"
        cli_args.antidebug = "Y"
        cli_args.antivm = "Y"
        cli_args.selfmod = "Y"
        cli_args.compile = "Y"
        cli_args.velimatix = "Y"
        cli_args.veli_level = 2
        cli_args.double_compile = "Y"
        cli_args.kramer = "N"
        cli_args.cjk_vars = "N"
        cli_args.matrix = "Y"
        cli_args.emoji_obf = "N"
        cli_args.homoglyph = "N"
        cli_args.rare_unicode = "N"
        cli_args.zalgo = "Y"
        cli_args.whitespace_obf = "N"
        cli_args.blank_padding = "N"
        cli_args.hyperion = "Y"
        cli_args.camouflage = "Y"
        cli_args.math_opaque = "Y"
        cli_args.dyn_strings = "Y"
        cli_args.anti_dump = "Y"
        cli_args.vm_obf = "Y"
        cli_args.vm_level = 3
        cli_args.dec_trap = "Y"
        cli_args.var_split = "Y"
        cli_args.str_frag = "Y"
        cli_args.debug_poison = "Y"
        cli_args.spoof_meta = "Y"
        cli_args.force_py = "off"

    return targets, is_batch, custom_out, _setup


def prompt_feature_flags(cli_args):
    """Interactive step-by-step protection prompts (original order preserved).

    Runs only in interactive mode. Returns a dict of resolved choices that
    cli.get_args_or_prompt consumes through its is_cli_mode ternaries.
    """
    _rule("LAYER TUNING")
    moreobf = cli_args.moreobf or _prompt_input(" MORE OBF? (y/n): ")
    antidebug = cli_args.antidebug or _prompt_input(" ANTI DEBUG? (y/n): ")
    antivm = getattr(cli_args, 'antivm', None) or _prompt_input(" ANTI VM & SANDBOX? (y/n): ")
    selfmodify = cli_args.selfmod or _prompt_input(" SELF-MODIFYING CODE? (y/n): ")
    method = cli_args.compile or _prompt_input(" COMPILE? (y/n): ")
    velimatix = cli_args.velimatix or _prompt_input(" VELIMATIX ENGINE? (y/n): ")

    veli_level = 1
    if velimatix.upper() == "Y":
        if cli_args.veli_level is not None:
            veli_level = cli_args.veli_level
        else:
            while True:
                try:
                    veli_level = int(_prompt_input(" VELIMATIX LEVEL (1-3): "))
                    if 1 <= veli_level <= 3:
                        break
                    _v(" ENTER 1, 2, OR 3")
                except ValueError:
                    _v(" INVALID")

    double_compile = "N"
    if method.upper() == "Y" and velimatix.upper() == "Y":
        double_compile = cli_args.double_compile or _prompt_input(" DOUBLE COMPILE (Veli wrap)? (y/n): ")

    kramer_wrap_choice = cli_args.kramer or _prompt_input(" KRAMER OUTER SHIELD (Kyrie Eleison)? (y/n): ")
    cjk_choice = cli_args.cjk_vars or _prompt_input(" CJK CHINESE IDENTIFIERS & PYCOOL DOCSTRINGS? (y/n): ")

    # New Obfuscation Modes
    matrix_choice = cli_args.matrix or _prompt_input(" MATRIX DEEP FUSION (Hybrid Variables + Fused 3-Track Shield)? (y/n): ")
    emoji_obf_choice = cli_args.emoji_obf or _prompt_input(" EMOJI OBFUSCATION (code -> Animal emoji stream)? (y/n): ")
    homoglyph_choice = cli_args.homoglyph or _prompt_input(" HOMOGLYPH NAMES (Cyrillic/Greek lookalikes: a/o/e)? (y/n): ")
    rare_unicode_choice = cli_args.rare_unicode or _prompt_input(" RARE UNICODE NAMES (CJK Ext-B Ancient glyphs)? (y/n): ")
    zalgo_choice = getattr(cli_args, 'zalgo', None) or _prompt_input(" ZALGO COMBINING MARKS (Extreme Diacritics Cascade)? (y/n): ")
    whitespace_obf_choice = cli_args.whitespace_obf or _prompt_input(" WHITESPACE OBFUSCATION (code -> Invisible space/tab)? (y/n): ")
    blank_padding_choice = getattr(cli_args, 'blank_padding', None) or getattr(cli_args, 'blank_lines', None) or _prompt_input(" BLANK LINES PADDING (Screen Blanker 300+ empty lines)? (y/n): ")
    hyperion_choice = getattr(cli_args, 'hyperion', None) or _prompt_input(" HYPERION ENGINE (Builtin/Import/Var token remap + Chunk shell)? (y/n): ")
    camouflage_choice = getattr(cli_args, 'camouflage', None) or _prompt_input(" HYPERION CAMOUFLAGE (Fake Scientific Simulation Class)? (y/n): ")
    math_opaque_choice = getattr(cli_args, 'math_opaque', None) or _prompt_input(" MATHEMATICAL OPAQUE PREDICATES (Number theory invariants)? (y/n): ")
    dyn_strings_choice = getattr(cli_args, 'dyn_strings', None) or _prompt_input(" DYNAMIC PER-CALLSITE STRING XOR (Zero global table)? (y/n): ")
    antidump_choice = getattr(cli_args, 'anti_dump', None) or _prompt_input(" IN-MEMORY ANTI-DUMP & GC SCRUBBER? (y/n): ")
    vm_obf_choice = getattr(cli_args, 'vm_obf', None) or _prompt_input(" VM VIRTUALIZATION ENGINE? (y/n): ")
    dectrap_choice = getattr(cli_args, 'dec_trap', None) or getattr(cli_args, 'dectrap', None) or _prompt_input(" DECOMPILER TRAPS (Break uncompyle6/decompyle3/pycdc)? (y/n): ")
    varsplit_choice = getattr(cli_args, 'var_split', None) or _prompt_input(" VARIABLE SECRET SHARING (XOR Split local ints)? (y/n): ")
    strfrag_choice = getattr(cli_args, 'str_frag', None) or _prompt_input(" STRING FRAGMENTATION (Decoy pool + dynamic assembly)? (y/n): ")
    debugpoison_choice = getattr(cli_args, 'debug_poison', None) or _prompt_input(" DECEPTIVE DEBUG POISONING (Silent key degradation)? (y/n): ")
    spoofmeta_choice = getattr(cli_args, 'spoof_meta', None) or _prompt_input(" METADATA & CO_FILENAME SPOOFING? (y/n): ")
    exotic_pools_choice = getattr(cli_args, 'exotic_pools', None) or _prompt_input(" EXOTIC UNICODE POOLS (Tangut/Egyptian/CJK-ExtG identifiers)? (y/n): ")
    base4096_choice = getattr(cli_args, 'base4096', None) or _prompt_input(" BASE4096 GLYPH ENCODING (12-bit astral stream)? (y/n): ")
    bit_matrix_choice = getattr(cli_args, 'bit_matrix', None) or _prompt_input(" BIT-MATRIX BYTE TRANSFORM (SBox/rotation/LCG)? (y/n): ")

    return {
        "moreobf": moreobf,
        "antidebug": antidebug,
        "antivm": antivm,
        "selfmodify": selfmodify,
        "method": method,
        "velimatix": velimatix,
        "veli_level": veli_level,
        "double_compile": double_compile,
        "kramer": kramer_wrap_choice,
        "cjk": cjk_choice,
        "matrix": matrix_choice,
        "emoji_obf": emoji_obf_choice,
        "homoglyph": homoglyph_choice,
        "rare_unicode": rare_unicode_choice,
        "zalgo": zalgo_choice,
        "whitespace_obf": whitespace_obf_choice,
        "blank_padding": blank_padding_choice,
        "hyperion": hyperion_choice,
        "camouflage": camouflage_choice,
        "math_opaque": math_opaque_choice,
        "dyn_strings": dyn_strings_choice,
        "anti_dump": antidump_choice,
        "vm_obf": vm_obf_choice,
        "dec_trap": dectrap_choice,
        "var_split": varsplit_choice,
        "str_frag": strfrag_choice,
        "debug_poison": debugpoison_choice,
        "spoof_meta": spoofmeta_choice,
        "exotic_pools": exotic_pools_choice,
        "base4096": base4096_choice,
        "bit_matrix": bit_matrix_choice,
    }


def ask_force_python():
    """Interactive FORCE PYTHON VERSION prompt pair. Returns (choice, version)."""
    force_py_choice = _prompt_input(" FORCE PYTHON VERSION? (y/n): ")
    forced_py_ver = ""
    if force_py_choice.upper() == "Y":
        cur_v = f"{sys.version_info.major}.{sys.version_info.minor}"
        forced_py_ver = _prompt_input(f" ENTER PY VERSION (default {cur_v}): ").strip()
        if not forced_py_ver:
            forced_py_ver = cur_v
    return force_py_choice, forced_py_ver


def ask_build_extras(_setup, is_batch, debug_map_arg, max_ram, max_cores, custom_out):
    """Interactive debug-map / resource-cap / output-path prompts.

    Guards mirror the original inline conditions exactly (_setup != "1",
    is_batch for the output path). Returns updated
    (debug_map_arg, max_ram, max_cores, custom_out).
    """
    if debug_map_arg is None and _setup != "1":
        dbg_choice = _prompt_input(" GENERATE DEBUG MAP (.json)? (y/n): ")
        if dbg_choice.upper() == "Y":
            debug_map_arg = "AUTO"

    if max_ram is None and _setup != "1":
        ram_inp = _prompt_input(" MAX RAM LIMIT IN MB (press Enter for unlimited): ").strip()
        if ram_inp.isdigit():
            max_ram = int(ram_inp)
    if max_cores is None and _setup != "1":
        core_inp = _prompt_input(" MAX CPU CORES (press Enter for auto): ").strip()
        if core_inp.isdigit():
            max_cores = int(core_inp)

    if not is_batch and custom_out is None and _setup != "1":
        out_inp = _prompt_input(" CUSTOM OUTPUT PATH (press Enter for default): ").strip()
        if out_inp:
            custom_out = out_inp

    return debug_map_arg, max_ram, max_cores, custom_out


def ask_encryption_password():
    """Interactive payload encryption password prompt (secret input)."""
    return _prompt_input(" PASSWORD ENCRYPTION (press Enter for obfuscation-only): ", secret=True).strip()

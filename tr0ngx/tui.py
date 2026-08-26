# Interactive TUI layer (extracted from the original monolith dispatcher).
# ═══════════════════════════════════════════════════════════════
# Full UI/UX remake grounded in the ui-ux-pro-max design system:
#   style     Dark Mode (OLED) - deep slate surfaces, high contrast text
#   palette   fg #F8FAFC · muted #94A3B8 · border #475569
#             accent/run #22C55E · warn #FACC15 · danger #EF4444
#   mood      terminal / cli / hacker / monospace precision
#
# The block-letter logo renders the brand "Tr0ngX". Because 5x5 block
# letters have no case distinction, the camelCase brand renders as
# "TR0NGX" - the canonical uppercase form of the same word.
#   T  R  0  N  G  X   (left → right)
#
# Prompt ORDER and semantics are preserved from the original flows;
# only rendering moved. All user-facing text is English.

# stdlib wiring
import os
import sys
import ast
import time
import threading
from typing import List, Tuple, Optional

# pure UI/diagnostic helpers
from .diagnostics import (
    _v,
    _gradient_text,
    _prompt_input,
)

# input source security validation
from .names import _validate_input_source

# Static edge toward cli: the batch file-selection loop reuses
# _resolve_input_files, which stays owned by cli.py next to the argparse
# path. Safe because cli.py only imports this module lazily at call time,
# so the package graph stays acyclic.
from .cli import _resolve_input_files

# ── design tokens (ui-ux-pro-max: Dark OLED / slate-emerald) ─────────
_W = 76                          # content width, consistent rhythm everywhere
_FG = (248, 250, 252)            # #F8FAFC foreground
_MUTED = (148, 163, 184)         # #94A3B8 secondary text
_BORDER = (71, 85, 105)           # #475569 borders/rules
_BORDER_DIM = (51, 65, 85)        # darker inner rule for layered depth
_ACC1 = (34, 197, 94)             # #22C55E emerald (ramp start)
_ACC2 = (56, 189, 248)            # #38BDF8 sky    (ramp mid)
_ACC3 = (140, 80, 255)            # #8C50FF violet(ramp end)
_OK = (34, 197, 94)
_WARN = (250, 204, 21)
_DANGER = (239, 68, 68)
_INFO = (56, 189, 248)

try:
    from pystyle import Col as _Col
    _GREEN = _Col.green
    _YELLOW = _Col.yellow
    _RED = _Col.red
    _GREY = _Col.dark_gray
    _WHITE = _Col.white
    _RESET = _Col.reset
except Exception:
    _GREEN, _YELLOW, _RED = "\033[92m", "\033[93m", "\033[91m"
    _GREY, _WHITE, _RESET = "\033[90m", "\033[97m", "\033[0m"


# ══════════════════════════════════════════════════════════════════
#  Low-level colour & output primitives
# ══════════════════════════════════════════════════════════════════
def _rgb(c: tuple) -> str:
    return f"\033[38;2;{c[0]};{c[1]};{c[2]}m"


def _g(text: str) -> str:
    """Primary brand gradient (emerald -> sky)."""
    return _gradient_text(text, _ACC1, _ACC2)


def _gradient_str(text: str, stops) -> str:
    """Multi-stop horizontal per-character gradient."""
    if not text:
        return ""
    total = max(1, len(text) - 1)
    out = []
    for i, ch in enumerate(text):
        t = i / total
        seg = t * (len(stops) - 1)
        idx = min(len(stops) - 2, int(seg))
        tt = seg - idx
        a, b = stops[idx], stops[idx + 1]
        c = (int(a[0] + (b[0] - a[0]) * tt),
             int(a[1] + (b[1] - a[1]) * tt),
             int(a[2] + (b[2] - a[2]) * tt))
        out.append(f"\033[38;2;{c[0]};{c[1]};{c[2]}m{ch}")
    return "".join(out) + _RESET


def _dim(text: str) -> str:
    return f"{_rgb(_MUTED)}{text}{_RESET}"


def _fg(text: str) -> str:
    return f"{_rgb(_FG)}{text}{_RESET}"


def _accent(text: str) -> str:
    return f"{_rgb(_ACC1)}{text}{_RESET}"


def _info_c(text: str) -> str:
    return f"{_rgb(_INFO)}{text}{_RESET}"


def _warn_c(text: str) -> str:
    return f"{_rgb(_WARN)}{text}{_RESET}"


def _danger_c(text: str) -> str:
    return f"{_rgb(_DANGER)}{text}{_RESET}"


def _border_ch(ch: str) -> str:
    return f"{_rgb(_BORDER)}{ch}{_RESET}"


def _border_dim_ch(ch: str) -> str:
    return f"{_rgb(_BORDER_DIM)}{ch}{_RESET}"


def _out(text: str = "") -> None:
    """Direct console write - bypasses the [TR0NGX] stage-tag logger so UI
    frames stay perfectly aligned and colours render untouched."""
    sys.stdout.write(text + "\n")
    try:
        sys.stdout.flush()
    except Exception:
        pass


def _out_raw(text: str = "") -> None:
    """Write without trailing newline - used by inline animations."""
    sys.stdout.write(text)
    try:
        sys.stdout.flush()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
#  Animations
# ══════════════════════════════════════════════════════════════════
_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def _spinner(done_event: threading.Event, label: str, color=_ACC1) -> None:
    """Async braille spinner. Stops the instant done_event is set."""
    i = 0
    while not done_event.is_set():
        frame = _SPINNER_FRAMES[i % len(_SPINNER_FRAMES)]
        _out_raw(f"\r  {_rgb(color)}{frame}{_RESET}  {_dim(label)}")
        i += 1
        time.sleep(0.06)
    _out_raw("\r" + " " * (len(label) + 8) + "\r")


def _typewriter(text: str, delay: float = 0.010) -> None:
    """Per-character reveal for hero taglines."""
    for ch in text:
        _out_raw(ch)
        time.sleep(delay)
    _out_raw("\n")


def _mini_bar(active: int, total: int, width: int = 24, color=_ACC1) -> str:
    """Static mini progress bar string (no newline)."""
    if total <= 0:
        return ""
    pct = min(1.0, active / total)
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"{_rgb(color)}{bar}{_RESET}"


# ══════════════════════════════════════════════════════════════════
#  Console init
# ══════════════════════════════════════════════════════════════════
def _init_console() -> None:
    """Best-effort console polish: clear screen, enable VT processing,
    pin a monospace font on legacy conhost. Every step is optional."""
    if os.name != "nt":
        try:
            _out("\033[2J\033[H")
        except Exception:
            pass
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-11)
        _out("\033[2J\033[H")
        mode = ctypes.c_ulong()
        if k32.GetConsoleMode(h, ctypes.byref(mode)):
            k32.SetConsoleMode(h, mode.value | 0x0004)

        class COORD(ctypes.Structure):
            _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

        class FONT(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong),
                        ("nFont", ctypes.c_ulong),
                        ("dwFontSize", COORD),
                        ("FontFamily", ctypes.c_uint),
                        ("FontWeight", ctypes.c_uint),
                        ("FaceName", ctypes.c_wchar * 32)]
        f = FONT()
        f.cbSize = ctypes.sizeof(FONT)
        f.dwFontSize.X = 0
        f.dwFontSize.Y = 18
        f.FontWeight = 500
        f.FaceName = "Consolas"
        k32.SetCurrentConsoleFontEx(h, False, ctypes.byref(f))
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
#  Block-letter logo & hero banner
# ══════════════════════════════════════════════════════════════════
# Block-letter ASCII art rendering of the brand "Tr0ngX".
# Reads left→right as:  T  R  0  N  G  X
# (5x5 block letters have no case distinction, so the camelCase
#  brand "Tr0ngX" canonicalises to "TR0NGX" in block form.)
_LOGO_ROWS = [
    "████████     █████   ████    ██   ██  ██████  ██   ██",
    "   ██       ██   ██  ██  ██   ██  ██  ██      ██  ██ ",
    "   ██       ███████  ██   ██  █████   ██████  █████  ",
    "   ██       ██   ██  ██  ██   ██  ██  ██      ██  ██ ",
    "   ██  ██   ██   ██  ████    ██   ██  ██████  ██   ██",
]


def _logo() -> None:
    """Per-character multi-stop gradient (emerald → sky → violet)."""
    stops = (_ACC1, _ACC2, _ACC3)
    total = max(len(r) for r in _LOGO_ROWS)
    for r in _LOGO_ROWS:
        parts = []
        for x, ch in enumerate(r):
            if ch == " ":
                parts.append(" ")
                continue
            t = min(1.0, max(0.0, x / max(1, total - 1)))
            seg = t * (len(stops) - 1)
            i = min(len(stops) - 2, int(seg))
            tt = seg - i
            a, b = stops[i], stops[i + 1]
            c = (int(a[0] + (b[0] - a[0]) * tt),
                 int(a[1] + (b[1] - a[1]) * tt),
                 int(a[2] + (b[2] - a[2]) * tt))
            parts.append(f"\033[38;2;{c[0]};{c[1]};{c[2]}m{ch}")
        _out("".join(parts) + _RESET)


def _gradient_rule(width: int = _W, ch: str = "─", stops=None) -> str:
    if stops is None:
        stops = (_ACC1, _ACC2, _ACC3)
    return _gradient_str(ch * width, stops)


def _banner() -> None:
    """Hero: gradient double-rule frame, multi-stop gradient logo,
    centred gradient tagline, bottom gradient rule."""
    sub = "python code protection suite  ·  interactive setup  ·  v4.0"
    sp = max(0, (_W - len(sub)) // 2)
    _out("")
    _out("  " + _gradient_rule(_W - 4, "═"))
    _out("")
    _logo()
    _out("")
    _out(" " * sp + _g(sub))
    _out("")
    _out("  " + _gradient_rule(_W - 4, "═"))
    _out("")


def _section(label: str) -> None:
    """Section divider with ◆ badge embedded in a double-edge rule."""
    _out("")
    inner = _W - 6
    badge = f"  ◆  {label}  "
    pad_after = max(2, inner - len(label) - 6)
    line = (
        "  "
        + _border_dim_ch("──")
        + _border_ch("─" * 2)
        + _g(badge)
        + _border_ch("─" * pad_after)
        + _border_dim_ch("──")
    )
    _out(line)


# ══════════════════════════════════════════════════════════════════
#  Panels, menus, checklists
# ══════════════════════════════════════════════════════════════════
def _panel_open(inner: int) -> str:
    return "  " + _border_ch("╭") + _border_ch("─" * (inner + 2)) + _border_ch("╮")


def _panel_close(inner: int) -> str:
    return "  " + _border_ch("╰") + _border_ch("─" * (inner + 2)) + _border_ch("╯")


def _panel_mid(inner: int) -> str:
    return "  " + _border_ch("├") + _border_ch("─" * (inner + 2)) + _border_ch("┤")


def _menu(rows, icons: Optional[List[str]] = None) -> None:
    """Rounded option list with optional icon prefix per row."""
    inner = _W - 6
    _out(_panel_open(inner))
    for idx, (num, label, desc) in enumerate(rows):
        icon = icons[idx] if icons and idx < len(icons) else " "
        bullet = _accent(f"[{num}]")
        label_str = _fg(label)
        sep = _dim("·")
        desc_str = _dim(desc)
        icon_str = _accent(icon) if icon != " " else " "
        content = f"  {icon_str}  {bullet}  {label_str}  {sep} {desc_str}"
        visual_len = 2 + 1 + 2 + 3 + 2 + len(label) + 2 + 1 + 1 + 1 + len(desc)
        pad = max(0, inner - visual_len)
        _out("  " + _border_ch("│") + content + " " * pad + _border_ch("│"))
    _out(_panel_close(inner))


def _checklist(title: str, pairs) -> None:
    """Two-column ON/OFF state panel + density bar at the bottom."""
    inner = _W - 6
    cells = []
    active_count = 0
    total_count = 0
    for name, on in pairs:
        total_count += 1
        if str(on).upper() == "Y":
            mark = _accent("✓")
            state = _accent("ON ")
            active_count += 1
        else:
            mark = _dim("·")
            state = _dim("off")
        cells.append((name, mark, state))

    _out(_panel_open(inner))
    title_pad = max(0, inner - len(title) - 1)
    _out("  " + _border_ch("│") + " " + _g(title) + " " * title_pad + _border_ch("│"))
    _out(_panel_mid(inner))

    for i in range(0, len(cells), 2):
        left_n, left_m, left_s = cells[i]
        left_block = f" {left_m} {left_n:<22} {left_s}"
        if i + 1 < len(cells):
            right_n, right_m, right_s = cells[i + 1]
            right_block = f" {right_m} {right_n:<22} {right_s}"
        else:
            right_block = ""
        used = len(left_block) + len(right_block)
        pad = max(0, inner - used)
        _out("  " + _border_ch("│") + left_block + right_block + " " * pad + _border_ch("│"))

    # density bar at the bottom of the panel
    _out(_panel_mid(inner))
    pct = active_count / max(1, total_count)
    bar_w = 24
    filled = int(bar_w * pct)
    bar = "█" * filled + "░" * (bar_w - filled)
    density_label = f" density: {active_count} / {total_count} layers active"
    bar_str = f" {_rgb(_ACC1)}{bar}{_RESET}"
    content = bar_str + _dim(density_label)
    pad = max(0, inner - len(density_label) - bar_w - 1)
    _out("  " + _border_ch("│") + content + " " * pad + _border_ch("│"))
    _out(_panel_close(inner))


def _summary_panel(cli_args, _setup: str, targets, is_batch: bool, custom_out) -> None:
    """Rich summary card: key-value rows + density progress bar."""
    names = {"1": "FAST", "2": "BALANCED", "3": "MAXIMUM ARSENAL", "4": "CUSTOM"}
    inner = _W - 6
    _out("")
    _out(_panel_open(inner))
    title = "  ◉  READY  ·  configuration locked  "
    title_pad = max(0, inner - len(title) + 4)
    _out("  " + _border_ch("│") + _g(title) + " " * title_pad + _border_ch("│"))
    _out(_panel_mid(inner))

    rows = [
        ("profile",   names.get(_setup, _setup)),
        ("ast mode",  str(getattr(cli_args, "mode", 0))),
        ("targets",   "%d file%s" % (len(targets), "s" if len(targets) != 1 else "")),
        ("scope",     "batch" if is_batch else "single"),
        ("output",    custom_out or "default"),
    ]
    for k, v in rows:
        klen = len(k) + 2  # 'key:'
        vlen = len(v) + 1
        content = f" {_dim(k + ':')} {_fg(v)}"
        pad = max(0, inner - klen - vlen - 1)
        _out("  " + _border_ch("│") + content + " " * pad + _border_ch("│"))

    # density bar inside summary too
    _out(_panel_mid(inner))
    pairs = _profile_pairs(cli_args)
    active = sum(1 for _, v in pairs if str(v).upper() == "Y")
    total = len(pairs)
    pct = active / max(1, total)
    bar_w = 24
    filled = int(bar_w * pct)
    bar = "█" * filled + "░" * (bar_w - filled)
    pct_str = f"{int(pct * 100):>3d}%"
    content = f" {_rgb(_ACC1)}{bar}{_RESET}  {_fg(pct_str)}  {_dim('protection density')}"
    visual_len = 1 + bar_w + 2 + 3 + 2 + len("protection density")
    pad = max(0, inner - visual_len)
    _out("  " + _border_ch("│") + content + " " * pad + _border_ch("│"))

    _out(_panel_close(inner))


def _footer() -> None:
    """Branded footer with double gradient rule."""
    _out("")
    _out("  " + _gradient_rule(_W - 4, "═"))
    brand = "tr0ngx · python code protection suite · stay paranoid"
    sp = max(0, (_W - len(brand)) // 2)
    _out(" " * sp + _dim(brand))
    _out("  " + _gradient_rule(_W - 4, "═"))
    _out("")


# ══════════════════════════════════════════════════════════════════
#  Status indicators
# ══════════════════════════════════════════════════════════════════
def _state_ok(msg: str) -> None:
    _out(f"  {_rgb(_OK)}●{_RESET}  {_fg(msg)}")


def _state_warn(msg: str) -> None:
    _out(f"  {_rgb(_WARN)}▲{_RESET}  {_warn_c(msg)}")


def _state_err(msg: str) -> None:
    _out(f"  {_rgb(_DANGER)}✗{_RESET}  {_danger_c(msg)}")


def _state_info(msg: str) -> None:
    _out(f"  {_rgb(_INFO)}◆{_RESET}  {_info_c(msg)}")


# ══════════════════════════════════════════════════════════════════
#  Profile pair extractor
# ══════════════════════════════════════════════════════════════════
def _profile_pairs(cli_args) -> list:
    keys = [
        ("AST mode %d" % getattr(cli_args, "mode", 0), None),
    ]
    flags = [
        ("compile", cli_args.compile),
        ("double-compile", cli_args.double_compile),
        ("velimatix L%d" % getattr(cli_args, "veli_level", 1), cli_args.velimatix),
        ("TVM virtualization", cli_args.vm_obf),
        ("anti-debug", cli_args.antidebug),
        ("anti-vm", cli_args.antivm),
        ("anti-dump", cli_args.anti_dump),
        ("self-modify", cli_args.selfmod),
        ("fused matrix", cli_args.matrix),
        ("camouflage", cli_args.camouflage),
        ("hyperion", cli_args.hyperion),
        ("math-opaque", cli_args.math_opaque),
        ("dyn-strings", cli_args.dyn_strings),
        ("dec-traps", cli_args.dec_trap),
        ("var-split", cli_args.var_split),
        ("str-frag", cli_args.str_frag),
        ("debug-poison", cli_args.debug_poison),
        ("spoof-meta", cli_args.spoof_meta),
        ("zalgo marks", cli_args.zalgo),
        ("cjk vars", cli_args.cjk_vars),
        ("homoglyph", cli_args.homoglyph),
        ("rare-unicode", cli_args.rare_unicode),
    ]
    return [(k, v) for k, v in flags]


# ══════════════════════════════════════════════════════════════════
#  Interactive entry
# ══════════════════════════════════════════════════════════════════
def run_interactive(cli_args):
    """Interactive entry: file/batch selection menu + protection profile menu.

    Returns (targets, is_batch, custom_out, _setup).
    """
    targets = []
    is_batch = False
    custom_out = cli_args.output

    _init_console()
    _banner()

    # ── INPUT MODE ─────────────────────────────────────────────────
    _section("INPUT MODE")
    _menu(
        [
            ("1", "SINGLE FILE", "protect one .py script"),
            ("2", "BATCH / TREE", "globs, many files or a whole directory"),
        ],
        icons=["▸", "⚡"],
    )
    file_mode_choice = _prompt_input(" Choose (1/2, default 1): ").strip()
    if file_mode_choice == "2":
        is_batch = True
        while True:
            batch_inp = _prompt_input(
                " Directory / glob / files (e.g. src/, *.py): "
            ).strip().strip('"').strip("'")
            rec_inp = _prompt_input(
                " Recurse subdirectories? (y/n, default n): "
            ).strip().upper()
            is_rec = (rec_inp == "Y")

            done = threading.Event()
            t = threading.Thread(
                target=_spinner,
                args=(done, "scanning filesystem for .py sources"),
                daemon=True,
            )
            t.start()
            try:
                targets = _resolve_input_files(
                    inputs=batch_inp,
                    directory=batch_inp if os.path.isdir(batch_inp) else None,
                    recursive=is_rec,
                )
                done.set()
                t.join()
                if targets:
                    _state_ok("discovered %d Python files for batch obfuscation" % len(targets))
                    for t_idx, t in enumerate(targets[:10], 1):
                        _out(_dim(f"       {t_idx:>2}. {t['rel']}"))
                    if len(targets) > 10:
                        _out(_dim(f"       ... and {len(targets) - 10} more."))
                    break
                else:
                    _state_warn("no matching .py files found - try again")
            except Exception as e:
                done.set()
                t.join()
                _state_err(f"file discovery failed: {e} - try again")

        out_dir_inp = _prompt_input(
            " Output directory (default tr0ngx_dist/): "
        ).strip().strip('"').strip("'")
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
                _state_ok("loaded %s (%d bytes)" % (_file, len(raw_code)))
                break
            except Exception as e:
                _state_err(f"syntax/security check failed: {e}")
                _file = _prompt_input(" Enter file path again: ").strip().strip('"').strip("'")

    # ── PROTECTION PROFILE ─────────────────────────────────────────
    _section("PROTECTION PROFILE")
    _menu(
        [
            ("1", "FAST",        "mode 1 AST pass + dynamic strings"),
            ("2", "BALANCED",    "mode 2 + AEAD compile + Velimatix L2 + matrix"),
            ("3", "MAX ARSENAL", "mode 3 + TVM L3 + camouflage + traps + zalgo"),
            ("4", "CUSTOM",      "hand-tune every layer step by step"),
        ],
        icons=["⚡", "⚖", "☠", "⚙"],
    )
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

    if _setup in ("1", "2", "3"):
        names = {"1": "FAST", "2": "BALANCED", "3": "MAXIMUM ARSENAL"}
        _checklist("PROFILE LOCKED  ·  " + names[_setup],
                   _profile_pairs(cli_args))
        _summary_panel(cli_args, _setup, targets, is_batch, custom_out)

    _footer()

    return targets, is_batch, custom_out, _setup


# ══════════════════════════════════════════════════════════════════
#  Layer tuning
# ══════════════════════════════════════════════════════════════════
def prompt_feature_flags(cli_args):
    """Interactive step-by-step protection prompts (original order preserved).

    Runs only in interactive mode. Returns a dict of resolved choices that
    cli.get_args_or_prompt consumes through its is_cli_mode ternaries.
    """
    _section("LAYER TUNING")
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
                    _state_warn("ENTER 1, 2, OR 3")
                except ValueError:
                    _state_err("INVALID INPUT")

    double_compile = "N"
    if method.upper() == "Y" and velimatix.upper() == "Y":
        double_compile = cli_args.double_compile or _prompt_input(" DOUBLE COMPILE (Veli wrap)? (y/n): ")

    kramer_wrap_choice = cli_args.kramer or _prompt_input(" KRAMER OUTER SHIELD (Kyrie Eleison)? (y/n): ")
    cjk_choice = cli_args.cjk_vars or _prompt_input(" CJK CHINESE IDENTIFIERS & PYCOOL DOCSTRINGS? (y/n): ")

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


# ══════════════════════════════════════════════════════════════════
#  Build extras
# ══════════════════════════════════════════════════════════════════
def ask_force_python():
    """Interactive FORCE PYTHON VERSION prompt pair. Returns (choice, version)."""
    _section("RUNTIME TARGET")
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
    _section("PAYLOAD ENCRYPTION")
    return _prompt_input(
        " PASSWORD ENCRYPTION (press Enter for obfuscation-only): ",
        secret=True,
    ).strip()
# AUTO-SPLIT from tr0ngx_obfuscator.py (mechanical slice)
import os
import sys
import re
import time
import platform
import threading
import traceback
from getpass import getpass

from . import config as _cfg

# ═══════════════════════════════════════════════════════════════
# UI
# ═══════════════════════════════════════════════════════════════

dark = _cfg.Col.dark_gray
light = _cfg.Col.light_gray
purple = _cfg.Colors.StaticMIX((_cfg.Col.green, _cfg.Col.yellow))
bpurple = _cfg.Colors.StaticMIX((_cfg.Col.pink, _cfg.Col.blue, _cfg.Col.blue))

text = f"""
  TR0NGX x VELIMATIX - ULTIMATE OBFUSCATOR
  AST ENGINE v4.0 - MAXIMUM POWER EDITION

 ══════════ TR0NGX CORE ENGINE ══════════
  • STRING    : 6 STRATEGIES (LAMBDA/XOR/SPLIT/REVERSE/SHUFFLE/BYTEWISE)
  • INTEGER   : 8 STRATEGIES (BYTE/OFFSET/XOR/ARITHMETIC/SHIFT/NESTED)
  • CONTROL   : STATE MACHINE + TRY-CATCH + MATCH-CASE + JUNK DECOYS

 ══════════ VELIMATIX AST ENGINE ══════════
  • BI-OPAQUE  : PREDICATE INJECTION + ROADLINE GENERATION
  • EXCEPTION  : WHILE-LOOP + EXCEPTION JUMP CONTROL FLOW
  • CONTROL    : MATCH-CASE STATE MACHINE + JUNK CASES
  • CALL OBF   : BUILTIN -> GETATTR CHAIN RECONSTRUCTION
  • MUTATOR    : XOR CHAIN + LAMBDA WRAP + STACK ELEMENTS
  • CLONE      : FAKE METHOD COPIES + DEAD CODE INJECTION
  • BUILTIN    : FULL BUILTIN RENAME (60+ FUNCTIONS)
  • STRING     : BYTEWISE XOR + SHIFT + NOT ENCODING

 ══════════ PROTECTION MATRIX ══════════
  • ANTI-DEBUG    : 6-VECTOR DETECTION + CONTINUOUS MONITOR
  • ANTI-HOOK     : VELIMATIX SHIELD + EXEC/EVAL GUARD
  • ANTI-IMPORT   : META_PATH BLOCKER (15+ TOOLS BLOCKED)
  • ANTI-DUMP     : CHUNKED EXECUTION + SELF-MODIFYING
  • ANTI-DECOMPILE: PYCDC/UNCOMPYLE BLOCKER (8000+ JUNK)
  • ANTI-MARSHAL  : TYPE VERIFY + CALLER CHECK + GUARD

 ══════════ AEAD COMPILER ══════════
  • PACKAGING     : MARSHAL + XOR(x2) + ZLIB(x2) + BZ2 + BASE85
  • DERIVATION    : 8-PART SPLIT + DYNAMIC KEY DERIVATION
  • DOUBLE COMPILE: TR0NGX INSIDE VELIMATIX LOADER

  • MODE 1 : LOW    (FAST, BASIC PROTECTION)
  • MODE 2 : MEDIUM (RECOMMENDED, FULL OBF)
  • MODE 3 : HIGH   (MAXIMUM, ALL LAYERS)

 ══════════ KRAMER & HYPERION ENGINES ══════════
  • KYRIE ELEISON  : INDEX SHIFT + ASCII CAESAR OFFSET
  • DYNAMIC CLASS  : RUNTIME OBFUSCATED CLASS + FAKE ANNOTATIONS
  • HYPERION TOKEN : BUILTINS / SCOPE / MATH / STR SPLITTING
  • CAMOUFLAGE     : FAKE SCIENTIFIC CLASS SIMULATION
  • FORCE PYTHON   : LOCK EXECUTION TO SPECIFIC PY VERSION (3.10 - 3.14)
  • CJK / PYCOOL   : CHINESE IDENTIFIERS + PYCOOL WATERMARKS

 ══════════ UNICODE MATRIX ENGINES ══════════
  • EMOJI-OBF     : CODE -> EMOJI SEQUENCE ENCODER (U+1F400 ANIMAL)
  • HOMOGLYPH     : CYRILLIC/GREEK LOOKALIKE NAMES (a/o/e)
  • RARE-UNICODE  : CJK EXTENSION B + KANGXI RADICALS (龘 鱻 𪚥)
  • ZALGO MARKS   : EXTREME PEP 3131 COMBINING DIACRITICS CASCADE
  • WHITESPACE    : INVISIBLE SPACE/TAB BINARY BITFIELD MATRIX
"""

banner = f"""

⠐⠀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⡀⠀⠀⠀⠀⠀⢀⣀⢀⠀⠀⣀⣀⣀⣀⠀⣀⣀⣀⣀⢀⡀⠀⠀⠀⠀⢀⡈⠢
⠀⠈⠭⣿⠏⠈⢻⣿⡿⠛⠉⠁⠀⠁⠀⠀⠀⠀⠀⢈⣈⣤⣤⣤⣀⡀⠀⠀⠀⠊⡊⠓⡦⡀⠀⠀⠀⠀⠀⠀⡇⠈
⠀⠀⠒⣧⣦⣠⠞⠁⠀⠀⠀⠀⠀⠀⢀⣀⣤⣶⣿⠯⠽⠧⠼⠷⢶⠿⢓⣀⣀⣆⡀⣠⣈⠻⣦⡀⣀⣠⡀⠀⡇⠀
⠀⠰⣟⣷⡟⠁⠀⠀⠀⠀⠀⢀⡤⠖⢫⣍⢀⣾⣯⠀⣞⡆⠀⣏⢻⣠⣄⡀⠉⠙⣻⣿⡻⣷⡈⢻⣿⣿⣷⣾⡇⠀
⠀⢠⣶⡟⠁⠀⠀⠀⣀⣴⠚⠉⠀⣠⣿⠞⠋⠻⣿⡀⠀⠀⠀⠈⠙⢻⣟⠳⣆⠀⠙⢯⡛⣿⢻⡇⡟⢩⢟⡟⡇⠀
⠀⢸⣿⠀⠀⠀⡠⣾⣿⢉⡀⢀⡆⡿⢃⣀⠀⠀⠘⣷⣀⢠⡄⠀⠀⠀⣙⠓⣿⣶⡀⠀⠛⠻⣾⣴⣱⣣⢖⣱⡇⠀
⠀⠸⣿⣧⢤⡎⣰⣣⣶⡏⡧⣄⣵⡿⠭⠻⠃⠀⠀⢣⣹⠸⣿⣤⡐⠛⠛⠷⡆⠈⠑⠢⠤⣀⠹⣿⡿⠿⣿⡿⡇⠀
⠀⢈⡿⣻⠉⡇⡿⠟⢉⡇⠱⣿⡁⡇⠀⠀⢀⣀⠀⠸⣧⠰⡇⢈⣙⡧⣄⡰⣤⣀⣠⣶⠒⠉⠀⠈⣧⣀⠀⣿⡇⠀
⠀⠀⣀⠈⠶⣿⠁⠀⠘⠣⢻⠇⣳⣷⣶⣶⣿⡟⠀⠀⠙⢷⣿⠘⣽⣿⣿⣿⣿⣄⠀⢻⠀⠀⠀⠀⡸⡿⠤⣷⡇⠀
⠀⠐⠋⠀⢀⡿⠀⠘⠀⢰⢸⣿⡿⢿⣿⠏⢉⣇⠀⠀⠀⠀⠙⠃⣾⣿⣁⣈⡻⣿⣯⣿⡄⠀⠀⣶⣇⢹⣧⣿⡇⠀
⠀⠀⠄⠀⡹⣧⠄⠀⠀⠸⣿⣿⡁⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡇⠸⢻⠇⠀⠀⠀⡼⣿⣼⣿⣿⡇⠀
⠀⠐⣦⡤⡁⣿⠰⢠⠀⠀⢙⣇⠁⠻⣯⣍⡬⠏⠀⠀⠀⠠⠀⠀⠻⣧⣀⠼⢳⣠⣿⡄⢀⣠⡞⣴⣿⣿⠋⢨⡇⠀
⠀⠀⠿⠂⠄⡟⣇⢸⡄⠀⠘⠛⣷⢴⣺⣿⡍⠀⠀⠀⠀⠀⠀⠀⠀⢠⠠⣵⣾⢟⣃⡠⢾⡏⣼⠏⢸⡟⠛⣿⡇⠀
⠀⠐⣒⣀⣀⡟⠛⠾⢧⠀⠀⠀⢽⡙⠉⠐⠁⠀⠀⠀⢀⣴⣄⠀⠀⠀⠃⠛⣿⣹⠋⢀⣾⡼⠁⠀⢸⣿⣥⡿⡇⠀
⠀⠈⠛⣿⢟⢣⠀⠀⠨⣧⡀⠀⠏⣧⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣨⣼⣿⠀⢸⣿⠀⠀⠀⢸⡏⠀⣷⡇⠀
⠀⠠⡖⠀⠀⢸⠀⠀⢠⣿⣧⠀⠀⠸⣿⣟⡷⣶⣦⣤⠤⢤⣤⣤⣶⣶⢿⡟⢽⣏⠀⢸⣿⠀⠀⠀⠀⣷⠯⢿⡇⠀
⠀⢠⣶⣶⣦⣼⣰⠀⠀⡿⠹⣧⠀⠀⣿⣸⣧⣿⣨⢿⠷⠒⠚⠛⠛⠛⠚⠛⠺⠯⠤⠚⠛⠓⠚⠓⠒⠻⣦⠀⡇⠀
⠀⢸⣟⣿⣿⣿⠁⠀⠀⡇⠀⠞⣷⠀⠘⢿⣽⣿⣵⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⠁⡇⠀
⠀⢸⣿⣿⣿⣿⡆⠀⢀⣿⡷⡎⠉⢣⡀⠈⢿⡣⠻⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣖⡇⠀
⠀⢸⣿⣿⣿⣿⠀⢠⠾⠃⠁⢸⡄⠀⢷⠀⠀⠻⣤⣿⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⡇⠀
⠠⣈⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⢁⠄
"""


# ═══════════════════════════════════════════════════════════════
# ADVANCED PROFILER & REAL-TIME DIAGNOSTIC LOGGER
# ═══════════════════════════════════════════════════════════════

_cfg._EngineState.verbose_debug = False
_cfg._EngineState.profile_mode = False
_cfg._EngineState.strict_mode = False
_cfg._EngineState.log_file_path = None
_LOG_ENTRIES = []
_STAGE_ERRORS = []

def _get_current_ram_mb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


class _PeakRSSSampler:
    """Background RSS sampler for honest peak-memory reporting.

    DIAG FIX (2026-08): debug-map ram_mb previously recorded the RSS at stage
    END, missing in-stage transients (e.g. fused-matrix compile() peaked at
    ~8.6GB while end-of-stage RSS showed ~1.1GB). A daemon thread polls RSS at
    4Hz and _track_debug_stage reports the true per-stage peak as
    peak_ram_mb. Purely diagnostic - no behavioral change.
    """

    _INTERVAL = 0.25

    def __init__(self):
        self._samples = []          # (monotonic_ts, rss_mb)
        self._lock = threading.Lock()
        self._started = False

    def ensure_started(self):
        if self._started:
            return
        try:
            import psutil  # noqa: F401
        except Exception:
            return
        self._started = True

        def _run():
            proc = None
            try:
                import psutil
                proc = psutil.Process(os.getpid())
            except Exception:
                return
            while True:
                try:
                    mb = proc.memory_info().rss / (1024 * 1024)
                    with self._lock:
                        self._samples.append((time.monotonic(), mb))
                        # cap memory of the sampler itself (~2h at 4Hz)
                        if len(self._samples) > 30000:
                            del self._samples[:15000]
                except Exception:
                    return
                time.sleep(self._INTERVAL)

        threading.Thread(target=_run, daemon=True, name="trx-rss-sampler").start()

    def peak_since(self, ts: float):
        if not self._started:
            return None
        peak = None
        with self._lock:
            for s_ts, s_mb in reversed(self._samples):
                if s_ts < ts:
                    break
                if peak is None or s_mb > peak:
                    peak = s_mb
        return peak


_PEAK_RSS_SAMPLER = _PeakRSSSampler()


def _log_debug(msg: str, stage: str = None, duration: float = None, error: Exception = None, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    dur_str = f" [took {duration:.4f}s]" if duration is not None else ""
    stg_str = f" [{stage}]" if stage else ""
    ram_mb = _get_current_ram_mb()
    ram_str = f" [RAM: {ram_mb:.1f}MB]" if ram_mb > 0 else ""
    entry = f"[{ts}][{level}]{stg_str}{ram_str} {msg}{dur_str}"
    _LOG_ENTRIES.append(entry)

    if _cfg._EngineState.verbose_debug or level in ("ERROR", "WARNING") or _cfg._EngineState.profile_mode:
        if level == "ERROR":
            _v(_gradient_text(f"  [ERROR]{stg_str} {msg}{dur_str}{ram_str}", (255, 60, 60), (255, 120, 60)))
            if error is not None:
                tb_lines = traceback.format_exc().strip()
                _LOG_ENTRIES.append(tb_lines)
                for l in tb_lines.splitlines():
                    _v(f"    │ {l}")
        elif level == "WARNING":
            _v(_gradient_text(f"  [WARNING]{stg_str} {msg}{dur_str}", (255, 180, 40), (255, 220, 80)))
        elif _cfg._EngineState.verbose_debug:
            _v(_gradient_text(f"  [DEBUG]{stg_str} {msg}{dur_str}{ram_str}", (80, 180, 255), (140, 220, 255)))

def _log_stage_error(stage_name: str, exc: Exception, extra_info: dict = None):
    tb = traceback.format_exc()
    tb_lines = [l for l in tb.strip().splitlines() if l.strip()]
    loc_str = tb_lines[-2] if len(tb_lines) >= 2 else "Unknown location"
    
    error_record = {
        "stage": stage_name,
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "location": loc_str.strip(),
        "traceback": tb,
        "timestamp": time.time(),
        "ram_mb": round(_get_current_ram_mb(), 2),
        "extra_info": extra_info or {}
    }
    _STAGE_ERRORS.append(error_record)
    
    if "_DEBUG_MAP" in globals() and "errors" in _DEBUG_MAP:
        _DEBUG_MAP["errors"].append(error_record)

    _log_debug(f"{type(exc).__name__}: {exc} (at {loc_str.strip()})", stage=stage_name, error=exc, level="ERROR")
    
    if _cfg._EngineState.strict_mode:
        _v(_gradient_text(f"\n [STRICT MODE ABORT] Terminating immediately due to error in stage '{stage_name}'", (255, 30, 30), (255, 100, 30)))
        _v(f"  Exception: {type(exc).__name__}: {exc}")
        _v(f"  Traceback:\n{tb}\n")
        sys.exit(1)

def _print_profile_waterfall(total_elapsed: float, original_size: int, final_size: int):
    stages = _DEBUG_MAP.get("stages", [])
    if not stages and not _STAGE_ERRORS:
        return

    _v("")
    _v(" ══════════════════════ PERFORMANCE & BOTTLENECK PROFILE ══════════════════════")
    _v(f" {'STAGE':<34} {'TIME (s)':<12} {'% TOTAL':<10} {'SIZE DELTA':<14} {'STATUS'}")
    _v(" ─────────────────────────────────────────────────────────────────────────────")

    slowest_stage = None
    max_duration = -1.0

    for s in stages:
        stg_name = s.get("stage", "Unknown")
        dur = s.get("duration_seconds", 0.0)
        pct = (dur / total_elapsed * 100) if total_elapsed > 0 else 0
        delta = s.get("delta_bytes", 0)
        delta_str = f"+{delta:,} B" if delta >= 0 else f"-{abs(delta):,} B"
        status = "[OK]"

        if dur > max_duration:
            max_duration = dur
            slowest_stage = (stg_name, dur, pct)

        _v(f" {stg_name:<34} {dur:>8.4f}s    {pct:>6.1f}%    {delta_str:>12}    {status}")

    for err in _STAGE_ERRORS:
        _v(f" [ERROR] {err['stage']:<26} FAILED        --               --    [ERROR]")

    _v(" ─────────────────────────────────────────────────────────────────────────────")
    current_ram = _get_current_ram_mb()
    ram_str = f" | PEAK RAM: {current_ram:.1f} MB" if current_ram > 0 else ""
    _v(f" TOTAL TIME: {total_elapsed:.4f}s | EXPANSION: {original_size:,} B -> {final_size:,} B ({final_size/original_size if original_size>0 else 0:.1f}x){ram_str}")

    if slowest_stage and slowest_stage[1] > 0.1 and slowest_stage[2] >= 25.0:
        _v(f" [BOTTLENECK ADVISORY] Stage '{slowest_stage[0]}' took the longest ({slowest_stage[1]:.3f}s, {slowest_stage[2]:.1f}% of total).")
    if _STAGE_ERRORS:
        _v(f" [WARNING] Encountered {len(_STAGE_ERRORS)} stage exception(s). Run with --debug or inspect log file for tracebacks.")
    _v(" ═════════════════════════════════════════════════════════════════════════════")
    _v("")

def _export_log_file():
    if not _cfg._EngineState.log_file_path:
        return
    try:
        with open(_cfg._EngineState.log_file_path, "w", encoding="utf-8") as lf:
            lf.write(f"=== TR0NGX OBFUSCATOR EXECUTION & DIAGNOSTIC LOG ===\n")
            lf.write(f"Timestamp : {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            lf.write(f"Python    : {sys.version}\n")
            lf.write(f"Platform  : {platform.platform()}\n")
            lf.write(f"PID       : {os.getpid()}\n\n")
            lf.write("=== EXECUTION CHRONOLOGY ===\n")
            for entry in _LOG_ENTRIES:
                lf.write(entry + "\n")
            if _STAGE_ERRORS:
                lf.write("\n=== STAGE ERROR TRACEBACKS ===\n")
                for err in _STAGE_ERRORS:
                    lf.write(f"\n--- Stage: {err['stage']} ({err['exception_type']}) @ RAM {err['ram_mb']}MB ---\n")
                    lf.write(f"Message  : {err['message']}\n")
                    lf.write(f"Location : {err.get('location', '')}\n")
                    lf.write(f"Traceback:\n{err['traceback']}\n")
        _v(f" [DIAGNOSTIC LOG SAVED] {_cfg._EngineState.log_file_path}")
    except Exception as e:
        _v(f" WARNING: Failed to export log file: {e}")

_DEBUG_MAP = {
    "version": "4.0",
    "timestamp": None,
    "source_file": None,
    "output_file": None,
    "options": {},
    "renamed_functions": {},
    "renamed_builtins": {},
    "renamed_variables": {},
    "skipped_renames": [],
    "stages": [],
    "errors": []
}

def _track_debug_stage(name: str, duration_sec: float, initial_size: int, final_size: int, details: dict = None):
    delta = final_size - initial_size
    delta_str = f"+{delta:,} B" if delta >= 0 else f"-{abs(delta):,} B"
    _log_debug(f"Completed ({duration_sec:.4f}s, size: {initial_size:,} -> {final_size:,} B [{delta_str}])", stage=name, duration=duration_sec)
    # DIAG (2026-08): peak_ram_mb = true in-stage RSS maximum sampled by the
    # background sampler; ram_mb remains the end-of-stage RSS for continuity.
    try:
        _peak_mb = _PEAK_RSS_SAMPLER.peak_since(time.monotonic() - float(duration_sec))
    except Exception:
        _peak_mb = None
    _DEBUG_MAP["stages"].append({
        "stage": name,
        "duration_seconds": round(duration_sec, 4),
        "initial_size_bytes": initial_size,
        "final_size_bytes": final_size,
        "delta_bytes": delta,
        "ram_mb": round(_get_current_ram_mb(), 2),
        "peak_ram_mb": round(_peak_mb, 2) if _peak_mb else None,
        "details": details or {}
    })

def _is_agent_or_non_interactive():
    if os.environ.get("NO_COLOR") or os.environ.get("CI") or os.environ.get("ANTIGRAVITY_AGENT"):
        return True
    if any(k in os.environ for k in ("AGENT_ID", "CONTINUATION_ID", "AI_AGENT", "CLAUDE_CODE", "CRUSH_CLI")):
        return True
    try:
        if not sys.stdout.isatty():
            return True
    except Exception:
        return True
    return False

_cfg._EngineState.cli_quiet_mode = _is_agent_or_non_interactive()

def _clean_ansi(text: str) -> str:
    if not isinstance(text, str):
        return str(text)
    # Strip standard ANSI escape sequences \x1b[...]
    cleaned = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
    # Strip any leaked raw RGB color codes like [38;2;...m or [200;200;200m
    cleaned = re.sub(r'\[38;2;\d+;\d+;\d+m', '', cleaned)
    cleaned = re.sub(r'\[[0-9;]{2,}m', '', cleaned)
    return cleaned

def _gradient_text(text: str, start_rgb: tuple, end_rgb: tuple) -> str:
    """Smooth two-color gradient string via 24-bit TrueColor ANSI escapes."""
    if not isinstance(text, str) or not text:
        return str(text)
    if _cfg._EngineState.cli_quiet_mode:
        return text
    n = max(len(text) - 1, 1)
    res = []
    for i, ch in enumerate(text):
        r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * (i / n))
        g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * (i / n))
        b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * (i / n))
        res.append(f"\033[38;2;{r};{g};{b}m{ch}")
    return "".join(res) + "\033[0m"

def _format_symbol_tag(symbol: str) -> str:
    """Build the [TR0NGX] / [STAGE] tag with a sharp neon-cyberpunk palette."""
    if _cfg._EngineState.cli_quiet_mode:
        return f"[{symbol}]"
    if symbol == 'TR0NGX':
        # Letter-by-letter Multi-Stop TrueColor Neon Gradient: Cyan -> Sky -> Indigo -> Violet -> Fuchsia -> Magenta
        return "\033[1;38;2;0;235;255m[\033[1;38;2;0;255;255mT\033[38;2;60;210;255mR\033[38;2;130;150;255m0\033[38;2;190;100;255mN\033[38;2;240;65;235mG\033[38;2;255;50;180mX\033[1;38;2;255;40;180m]\033[0m"
    elif symbol in ('ERROR', 'FAIL'):
        return f"\033[1;38;2;255;40;40m[\033[1;38;2;255;80;60m{symbol}\033[1;38;2;255;40;40m]\033[0m"
    elif symbol in ('WARN', 'WARNING'):
        return f"\033[1;38;2;255;180;20m[\033[1;38;2;255;220;40m{symbol}\033[1;38;2;255;180;20m]\033[0m"
    elif symbol in ('PASS', 'OK', 'SAVED'):
        return f"\033[1;38;2;0;240;255m[\033[1;38;2;50;255;130m{symbol}\033[1;38;2;0;240;255m]\033[0m"
    else:
        sym_grad = _gradient_text(symbol, (0, 240, 255), (240, 80, 255))
        return f"\033[1;38;2;0;240;255m[{sym_grad}\033[1;38;2;240;80;255m]\033[0m"

def stage(text: str, symbol: str = 'TR0NGX', col1=light, col2=None) -> str:
    text_str = str(text)
    # Extract clean core text without any prior ANSI codes or symbols
    clean_text = _clean_ansi(text_str).strip()
    if clean_text.startswith(f"[{symbol}]"):
        clean_text = clean_text[len(f"[{symbol}]"):].strip()
    
    if _cfg._EngineState.cli_quiet_mode:
        return f"[{symbol}] {clean_text}"

    upper_text = clean_text.upper()
    if "ENTER FILE" in upper_text:
        # Ultra-striking Amber Gold to Hot Neon Magenta gradient for file input prompts
        gradient_body = _gradient_text(clean_text, (255, 225, 30), (255, 40, 150))
    elif "SAVED:" in upper_text or "SUCCESS" in upper_text or "COMPLETE" in upper_text:
        # Electric Cyan to Neon Spring Green gradient
        gradient_body = _gradient_text(clean_text, (0, 240, 255), (50, 255, 130))
    elif any(kw in upper_text for kw in ["WARNING", "ERROR", "SYNTAX ERROR", "NOT FOUND", "FAILED"]):
        # Fiery Crimson Red to Radiant Gold-Orange gradient
        gradient_body = _gradient_text(clean_text, (255, 45, 45), (255, 185, 25))
    elif any(kw in upper_text for kw in ["MODE", "LEVEL", "CORES", "RAM", "LIMIT"]):
        # Neon Sunset Orange to Electric Purple gradient
        gradient_body = _gradient_text(clean_text, (255, 175, 40), (220, 75, 255))
    elif "? (Y/N)" in upper_text or "?" in upper_text:
        # Neon Turquoise to Orchid Violet gradient
        gradient_body = _gradient_text(clean_text, (40, 215, 255), (205, 105, 255))
    elif any(kw in upper_text for kw in ["ORIGINAL:", "OUTPUT:", "TIME:", "FUSION:", "DEBUG MAP", "OBF:", "ANTI:", "COMPILE:", "KRAMER:", "CJK"]):
        # Ice Cyan to Soft Magenta gradient
        gradient_body = _gradient_text(clean_text, (100, 220, 255), (180, 120, 255))
    else:
        # Bright Cyan to Vivid Purple default gradient
        gradient_body = _gradient_text(clean_text, (60, 210, 255), (210, 95, 255))

    tag = _format_symbol_tag(symbol)
    return f" {tag} {gradient_body} "

_raw_input = input

def _safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except (UnicodeEncodeError, Exception):
        enc = getattr(sys.stdout, 'encoding', 'utf-8') or 'utf-8'
        safe_args = [
            a.encode(enc, errors='replace').decode(enc, errors='replace') if isinstance(a, str) else a
            for a in args
        ]
        print(*safe_args, **kwargs)

_raw_print = _safe_print

def _v_step(step, total, text):
    """Pretty per-stage log line with colors and aligned columns."""
    if _cfg._EngineState.cli_quiet_mode:
        _v(f" [{step}/{total}] {text}")
        return
    tag = _format_symbol_tag('TR0NGX')
    step_str = f"[{str(step):>{len(str(total))}}/{total}]"
    grad = _gradient_text(f"{step_str} {text}", (100, 220, 255), (180, 120, 255))
    _raw_print(f" {tag} {grad} ", flush=True)

def _v(x, *k):
    if isinstance(x, str) and ('\x1b' in x or x.startswith('[TR0NGX]')):
        return _raw_print(x, *k, flush=True)
    return _raw_print(stage(x), *k, flush=True)

def _prompt_input(x, secret: bool = False):
    formatted = stage(x)
    try:
        sys.stdout.write(formatted)
        sys.stdout.flush()
        if secret:
            return getpass("").strip().strip('"').strip("'")
        return _raw_input("").strip().strip('"').strip("'")
    except (UnicodeEncodeError, Exception):
        enc = sys.stdout.encoding or 'utf-8'
        safe_prompt = formatted.encode(enc, errors='replace').decode(enc, errors='replace')
        sys.stdout.write(safe_prompt)
        sys.stdout.flush()
        if secret:
            return getpass("").strip().strip('"').strip("'")
        return _raw_input("").strip().strip('"').strip("'")

def _show_banner():
    if _cfg._EngineState.cli_quiet_mode:
        return
    b = _cfg.Add.Add(text, banner, center=True)
    _raw_print(_cfg.Colorate.Diagonal(_cfg.Colors.DynamicMIX((purple, light)), b))



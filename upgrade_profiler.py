import os, sys, re

def upgrade_codebase(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add Profiler Globals & Logging Functions
    profiler_code = """
# ═══════════════════════════════════════════════════════════════
# ADVANCED PROFILER & REAL-TIME DIAGNOSTIC LOGGER
# ═══════════════════════════════════════════════════════════════

_VERBOSE_DEBUG = False
_PROFILE_MODE = False
_STRICT_MODE = False
_LOG_FILE_PATH = None
_LOG_ENTRIES = []
_STAGE_ERRORS = []

def _get_current_ram_mb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0

def _log_debug(msg: str, stage: str = None, duration: float = None, error: Exception = None, level: str = "INFO"):
    global _LOG_ENTRIES
    ts = time.strftime("%H:%M:%S")
    dur_str = f" [took {duration:.4f}s]" if duration is not None else ""
    stg_str = f" [{stage}]" if stage else ""
    entry = f"[{ts}][{level}]{stg_str} {msg}{dur_str}"
    _LOG_ENTRIES.append(entry)

    if _VERBOSE_DEBUG or level in ("ERROR", "WARNING") or _PROFILE_MODE:
        if level == "ERROR":
            _v(f" \033[91m[ERROR]{stg_str} {msg}{dur_str}\033[0m")
            if error is not None:
                tb_lines = traceback.format_exc().strip()
                _LOG_ENTRIES.append(tb_lines)
                if _VERBOSE_DEBUG:
                    for l in tb_lines.splitlines():
                        _v(f"   \033[90m│ {l}\033[0m")
        elif level == "WARNING":
            _v(f" \033[93m[WARNING]{stg_str} {msg}{dur_str}\033[0m")
        elif _VERBOSE_DEBUG:
            _v(f" \033[96m[DEBUG]{stg_str} {msg}{dur_str}\033[0m")

def _log_stage_error(stage_name: str, exc: Exception):
    global _STAGE_ERRORS
    tb = traceback.format_exc()
    _STAGE_ERRORS.append({
        "stage": stage_name,
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "traceback": tb,
        "timestamp": time.time()
    })
    _log_debug(f"{type(exc).__name__}: {exc}", stage=stage_name, error=exc, level="ERROR")
    if _STRICT_MODE:
        _v(f" \033[91m[STRICT MODE ABORT] Terminating due to error in stage '{stage_name}'\033[0m")
        sys.exit(1)

def _print_profile_waterfall(total_elapsed: float, original_size: int, final_size: int):
    stages = _DEBUG_MAP.get("stages", [])
    if not stages and not _STAGE_ERRORS:
        return

    _v(" \n ══════════════════════ PERFORMANCE & BOTTLENECK PROFILE ══════════════════════")
    _v(f" {'STAGE':<32} {'TIME (s)':<12} {'% TOTAL':<10} {'SIZE DELTA':<14} {'STATUS'}")
    _v(" ─────────────────────────────────────────────────────────────────────────────")

    slowest_stage = None
    max_duration = -1.0

    for s in stages:
        stg_name = s.get("stage", "Unknown")
        dur = s.get("duration_seconds", 0.0)
        pct = (dur / total_elapsed * 100) if total_elapsed > 0 else 0
        delta = s.get("delta_bytes", 0)
        delta_str = f"+{delta:,} B" if delta >= 0 else f"-{abs(delta):,} B"
        status = "\033[92m[OK]\033[0m"

        if dur > max_duration:
            max_duration = dur
            slowest_stage = (stg_name, dur, pct)

        _v(f" {stg_name:<32} {dur:>8.4f}s    {pct:>6.1f}%    {delta_str:>12}    {status}")

    for err in _STAGE_ERRORS:
        _v(f" \033[91m{err['stage']:<32} {'FAILED':>8}        --               --    [ERROR]\033[0m")

    _v(" ─────────────────────────────────────────────────────────────────────────────")
    current_ram = _get_current_ram_mb()
    ram_str = f" | PEAK RAM: {current_ram:.1f} MB" if current_ram > 0 else ""
    _v(f" TOTAL TIME: {total_elapsed:.4f}s | EXPANSION: {original_size:,} B -> {final_size:,} B ({final_size/original_size if original_size>0 else 0:.1f}x){ram_str}")

    if slowest_stage and slowest_stage[1] > 0.1 and slowest_stage[2] >= 25.0:
        _v(f" \033[93m[BOTTLENECK ADVISORY] Stage '{slowest_stage[0]}' took the longest ({slowest_stage[1]:.3f}s, {slowest_stage[2]:.1f}% of total).\033[0m")
    if _STAGE_ERRORS:
        _v(f" \033[91m[WARNING] Encountered {len(_STAGE_ERRORS)} stage exception(s). Run with --debug or inspect log file for tracebacks.\033[0m")
    _v(" ═════════════════════════════════════════════════════════════════════════════\n")

def _export_log_file():
    if not _LOG_FILE_PATH:
        return
    try:
        with open(_LOG_FILE_PATH, "w", encoding="utf-8") as lf:
            lf.write(f"=== TR0NGX OBFUSCATOR EXECUTION & DIAGNOSTIC LOG ===\\n")
            lf.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\\n\\n")
            for entry in _LOG_ENTRIES:
                lf.write(entry + "\\n")
            if _STAGE_ERRORS:
                lf.write("\\n=== STAGE ERROR TRACEBACKS ===\\n")
                for err in _STAGE_ERRORS:
                    lf.write(f"\\n--- Stage: {err['stage']} ({err['exception_type']}) ---\\n")
                    lf.write(err['traceback'] + "\\n")
        _v(f" ✓ DIAGNOSTIC LOG SAVED: {_LOG_FILE_PATH}")
    except Exception as e:
        _v(f" WARNING: Failed to export log file: {e}")
"""

    # Inject profiler code before _DEBUG_MAP definition
    if "_VERBOSE_DEBUG = False" not in content:
        content = content.replace('_DEBUG_MAP = {', profiler_code + '\n_DEBUG_MAP = {')

    # 2. Add CLI Flags in Argument Parser
    old_args = 'parser.add_argument("--debug-map", nargs="?", const="AUTO", default=None, help="Xuất bản đồ ánh xạ ký hiệu & thời gian từng stage ra file JSON (vd: --debug-map map.json)")'
    new_args = """parser.add_argument("--debug-map", nargs="?", const="AUTO", default=None, help="Xuất bản đồ ánh xạ ký hiệu & thời gian từng stage ra file JSON (vd: --debug-map map.json)")
    parser.add_argument("--debug", "-d", action="store_true", help="Bật chế độ debug chi tiết (in log micro-stages, traceback và cảnh báo lỗi)")
    parser.add_argument("--profile", action="store_true", help="Hiển thị bảng phân tích chi tiết hiệu năng (Profiling Waterfall & Bottleneck Analysis)")
    parser.add_argument("--log-file", type=str, default=None, help="Ghi toàn bộ log và chẩn đoán chi tiết ra file riêng (vd: --log-file debug.log)")
    parser.add_argument("--strict", action="store_true", help="Dừng tiến trình ngay khi gặp lỗi ở bất kỳ stage nào thay vì âm thầm bỏ qua")"""

    if "--profile" not in content:
        content = content.replace(old_args, new_args)

    # 3. Configure CLI flags in main()
    cli_config_marker = "is_cli_mode = bool(cli_args.input is not None)"
    cli_config_patch = """is_cli_mode = bool(cli_args.input is not None)

    global _VERBOSE_DEBUG, _PROFILE_MODE, _STRICT_MODE, _LOG_FILE_PATH
    if getattr(cli_args, 'debug', False):
        _VERBOSE_DEBUG = True
    if getattr(cli_args, 'profile', False):
        _PROFILE_MODE = True
    if getattr(cli_args, 'strict', False):
        _STRICT_MODE = True
    if getattr(cli_args, 'log_file', None):
        _LOG_FILE_PATH = cli_args.log_file.strip().strip('"').strip("'")"""

    if "global _VERBOSE_DEBUG" not in content:
        content = content.replace(cli_config_marker, cli_config_patch)

    # 4. Enhance stage tracking with logging & profiling
    content = content.replace(
        'except Exception as e:\n        _v(f" WARNING: Syntax transform skipped: {e}")',
        'except Exception as e:\n        _log_stage_error("1_syntax_transform", e)'
    )
    content = content.replace(
        'except Exception as e:\n            _v(f" WARNING: AST junk issue: {e}")\n            check = 5',
        'except Exception as e:\n            _log_stage_error("2_ast_junk_injection", e)\n            check = 5'
    )
    content = content.replace(
        'except Exception as e:\n            _v(f" WARNING: Double compile failed: {e}")',
        'except Exception as e:\n            _log_stage_error("7_double_compile_packaging", e)'
    )
    content = content.replace(
        'except Exception as e:\n            _v(f" WARNING: Fused matrix shield error: {e}")',
        'except Exception as e:\n            _log_stage_error("8_fused_matrix_shield", e)'
    )

    # 5. Call _print_profile_waterfall and _export_log_file before completion
    old_complete = '_v(" OBFUSCATION COMPLETE!")'
    new_complete = """if _PROFILE_MODE or _VERBOSE_DEBUG:
            _print_profile_waterfall(elapsed, original_size, file_size)
        _export_log_file()
        _v(" OBFUSCATION COMPLETE!")"""

    if "_print_profile_waterfall" not in content:
        content = content.replace(old_complete, new_complete)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Successfully upgraded {file_path} with Advanced Debugger & Profiler!")

if __name__ == "__main__":
    upgrade_codebase(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
    upgrade_codebase(r"C:\Users\trong\Downloads\procheck.py")

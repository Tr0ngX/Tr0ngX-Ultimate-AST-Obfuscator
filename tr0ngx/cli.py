# AUTO-SPLIT from tr0ngx_obfuscator.py (mechanical slice, imports pending repair)
# ═══════════════════════════════════════════════════════════════
# CLI PARSER & INTERACTIVE DISPATCHER
# ═══════════════════════════════════════════════════════════════

# stdlib wiring
import os
import sys
import glob
import argparse
import random

# mutable engine state: attribute access via the config module (never from-import
# the class name directly, so rebinds in config stay visible). Named _trx_cfg to
# avoid shadowing by main()'s local options dict.
from . import config as _trx_cfg

# pure UI/diagnostic helpers + log containers (cleared in place, never rebound)
from .diagnostics import (
    _v,
    _gradient_text,
    _prompt_input,
    _show_banner,
    _print_profile_waterfall,
    _export_log_file,
    _raw_print,
    _LOG_ENTRIES,
    _STAGE_ERRORS,
    _DEBUG_MAP,
)

# pystyle facade (with zero-crash fallbacks) lives in config
from .config import Col, Colors, Colorate, Box

# name generators & shared identifier state
from .names import (
    _used_names,
    _used_names_lock,
    _RareChars,
    _gen_exotic_name,
    _init_rare_chars,
    _init_combining_marks,
)

# velimatix utility classes reset between runs
from .velimatix import BiOpaqueUtils, MutatorUtils, ExceptionJumpUtils, ControlFlowUtils

# runtime symbol pool refresh
from .astpasses import _refresh_runtime_symbols

# pipeline last: it imports engines, never cli
from .pipeline import run_batch_obfuscation, obfuscate_single_target


def _apply_resource_limits(max_ram_mb: int = None, max_cores: int = None):
    """Giới hạn tài nguyên RAM và CPU Cores để chống lag hệ thống."""
    if max_cores and max_cores > 0:
        try:
            # Set CPU Affinity on Windows/Linux
            if hasattr(os, "sched_setaffinity"):
                os.sched_setaffinity(0, set(range(min(max_cores, os.cpu_count() or 1))))
            elif sys.platform == "win32":
                import ctypes
                mask = (1 << min(max_cores, 64)) - 1
                handle = ctypes.windll.kernel32.GetCurrentProcess()
                ctypes.windll.kernel32.SetProcessAffinityMask(handle, mask)
        except Exception:
            pass
        os.environ["OMP_NUM_THREADS"] = str(max_cores)
        os.environ["MKL_NUM_THREADS"] = str(max_cores)

    if max_ram_mb and max_ram_mb > 0:
        # Start a daemon thread to monitor RAM and trigger gc
        def _ram_watchdog():
            import gc, time
            while True:
                time.sleep(2)
                try:
                    import psutil
                    mem = psutil.Process().memory_info().rss / (1024 * 1024)
                    if mem > max_ram_mb:
                        gc.collect()
                except Exception:
                    gc.collect()
        import threading
        t = threading.Thread(target=_ram_watchdog, daemon=True)
        t.start()

def _parse_size_str(val):
    if val is None:
        return None
    if isinstance(val, int):
        return val
    val = str(val).strip().upper()
    if val.endswith("GB") or val.endswith("G"):
        return int(float(val.rstrip("GB").rstrip("G")) * 1024 * 1024 * 1024)
    if val.endswith("MB") or val.endswith("M"):
        return int(float(val.rstrip("MB").rstrip("M")) * 1024 * 1024)
    if val.endswith("KB") or val.endswith("K"):
        return int(float(val.rstrip("KB").rstrip("K")) * 1024)
    if val.isdigit():
        return int(val)
    return None

def _resolve_input_files(inputs=None, directory=None, recursive=False):
    """
    Discovers all target python files from list of inputs, glob patterns, or directory path.
    Returns list of dicts: [{'src': absolute_source_path, 'rel': relative_output_path}, ...]
    Excludes the tool's own outputs (tr0ngx-* files, tr0ngx_dist dirs, __pycache__) and
    preserves directory structure in 'rel' to prevent basename collisions in batch mode.
    """
    found = []
    seen = set()

    # Directory-name blacklist for batch walks. Source: Opy skip_path_fragments
    # rationale (Apache-2.0 research note) + pyminifier analyze.py unfiltered-walk
    # defect lesson - vendored/virtualenv trees must never enter the batch.
    _BATCH_DIR_BLACKLIST = frozenset({
        "__pycache__", "tr0ngx_dist", ".git", ".hg", ".svn",
        "venv", ".venv", "env", ".env", "virtualenv",
        "site-packages", "node_modules", ".tox", ".mypy_cache", ".pytest_cache",
        "dist", "build", "research_repos",
    })

    def _is_source_file(name: str) -> bool:
        # Case-insensitive extension match + .pyw support (audit fix: .PY was
        # silently skipped on case-sensitive comparison).
        low = name.lower()
        return low.endswith(".py") or low.endswith(".pyw")

    def _excluded(f_abs: str) -> bool:
        base = os.path.basename(f_abs)
        if base.startswith("tr0ngx-"):
            return True
        parts = f_abs.replace("/", os.sep).split(os.sep)
        return any(p.lower() in _BATCH_DIR_BLACKLIST for p in parts[:-1])

    def _add(f_path: str, rel_hint: str = None):
        f_abs = os.path.abspath(f_path)
        if f_abs in seen or _excluded(f_abs):
            return
        seen.add(f_abs)
        if rel_hint:
            found.append({"src": f_abs, "rel": rel_hint})
        else:
            try:
                found.append({"src": f_abs, "rel": os.path.relpath(f_abs, os.getcwd())})
            except ValueError:
                found.append({"src": f_abs, "rel": os.path.basename(f_abs)})

    if directory:
        d_abs = os.path.abspath(directory.strip().strip('"').strip("'"))
        if not os.path.isdir(d_abs):
            raise FileNotFoundError(f"Directory not found: {directory}")
        if recursive:
            for root, _, files in os.walk(d_abs):
                for f in files:
                    if _is_source_file(f):
                        f_abs = os.path.abspath(os.path.join(root, f))
                        rel = os.path.relpath(f_abs, d_abs)
                        if f_abs not in seen and not _excluded(f_abs):
                            seen.add(f_abs)
                            found.append({"src": f_abs, "rel": rel})
        else:
            for f in os.listdir(d_abs):
                if _is_source_file(f):
                    f_abs = os.path.abspath(os.path.join(d_abs, f))
                    if os.path.isfile(f_abs) and f_abs not in seen and not _excluded(f_abs):
                        seen.add(f_abs)
                        found.append({"src": f_abs, "rel": f})

    if inputs:
        raw_items = []
        if isinstance(inputs, str):
            if "," in inputs:
                raw_items = [p.strip() for p in inputs.split(",") if p.strip()]
            else:
                raw_items = inputs.split()
        elif isinstance(inputs, (list, tuple)):
            for it in inputs:
                if isinstance(it, str) and "," in it:
                    raw_items.extend([p.strip() for p in it.split(",") if p.strip()])
                else:
                    raw_items.append(str(it).strip())

        for item in raw_items:
            item_str = str(item).strip().strip('"').strip("'")
            if not item_str:
                continue
            if any(c in item_str for c in ("*", "?", "[", "]")):
                globbed = glob.glob(item_str, recursive=recursive)
                pattern_dir = os.path.dirname(os.path.abspath(item_str)) or os.getcwd()
                for g in sorted(globbed):
                    if _is_source_file(g) and os.path.isfile(g):
                        g_abs = os.path.abspath(g)
                        try:
                            rel_hint = os.path.relpath(g_abs, pattern_dir)
                        except ValueError:
                            rel_hint = os.path.basename(g_abs)
                        _add(g_abs, rel_hint)
            elif os.path.isdir(item_str):
                d_found = _resolve_input_files(directory=item_str, recursive=recursive)
                for df in d_found:
                    if df["src"] not in seen:
                        seen.add(df["src"])
                        found.append(df)
            elif os.path.isfile(item_str):
                _add(item_str)

    # Final collision guard: make every 'rel' unique by prefixing parent dirs
    rels_seen = {}
    for entry in found:
        r = entry["rel"].replace("\\", "/")
        if r in rels_seen:
            n = 2
            while f"{r}.{n}" in rels_seen:
                n += 1
            r = f"{r}.{n}"
        rels_seen[r] = True
        entry["rel"] = r

    return found

def get_args_or_prompt():
    parser = argparse.ArgumentParser(
        prog="procheck.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
╔══════════════════════════════════════════════════════════════════════════════╗
║        TR0NGX x VELIMATIX x KRAMER - ULTIMATE AST OBFUSCATOR        ║
║                    PYTHON CODE PROTECTION SUITE v4.0                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

CÔNG CỤ LÀM RỐI MÃ NGUỒN PYTHON ĐA TẦNG CỰC MẠNH:
  • Tầng 0: Hyperion Engine (Builtin remapping, token variable remap, math/str splitting)
  • Tầng 1: Tr0ngX AST Transformer (Biến đổi hằng số, chuỗi, số nguyên, logic)
  • Tầng 2: Velimatix Engine (BiOpaque predicates, Exception jump, Match-Case state machine)
  • Tầng 3: Trongdepzai Multi-Layer AST Obfuscation (Lớp 1..3)
  • Tầng 4: True VM Virtualization 2.0 (TVM: Polymorphic CPU, Randomized ISA & Encrypted V-Bytecode)
  • Tầng 5: Double Compile Bytecode Loader (marshal + XOR + zlib + bz2 + base85)
  • Tầng 6: Anti-Analysis Matrix (Anti-Debug, Anti-VM/Sandbox, In-Memory Anti-Dump, Self-Mod)
  • Tầng 7: Math Opaque & Dynamic Callsite XOR Strings
  • Tầng 8: Kramer Kyrie Eleison Outer Shield (Mã hóa dịch chuyển Caesar động + Class ảo)
  • Tầng 9: Tên biến tiếng Trung / CJK + Watermark bản quyền PyCool
  • Tầng 10: Emoji Obfuscation (Code → chuỗi emoji 🐀🐁🐂 + self-decoding loader)
  • Tầng 11: Homoglyph & Rare Unicode Names (Cyrillic/Greek & CJK Ext-B, Kangxi, Hieroglyphs)
  • Tầng 12: Whitespace Obfuscation (Code biến đổi thành không gian trắng space/tab binary)
  • Tầng 13: Extreme Zalgo Diacritics Shield (Chồng lớp dấu tổ hợp làm tê liệt decompiler GUI)
  • Tầng 14: Hyperion Scientific Class Camouflage (Ngụy trang lớp mô phỏng bộ nhớ khoa học)
  • Tầng 15: 3-Track Symbiotic Fused Matrix Shield (Kyrie + Emoji + Whitespace hợp nhất không phình dung lượng)
  • Tầng 16: Bedrock Decompiler Traps & Secret Sharing (Decompiler crash matrix, var-split XOR & string-frag pool)
  • Tầng 17: Deceptive Debug Poisoning & Metadata Spoofing (Trạng thái nhiễm độc ngầm & giả lập module stdlib)
        """,
        epilog="""
VÍ DỤ SỬ DỤNG:
  1. Chạy CLI đơn file:
     python tr0ngx_obfuscator.py -i script.py -o obf_script.py -m 3 --compile y --velimatix y --kramer y

  2. Chạy CLI nhiều file / Batch Obfuscation:
     python tr0ngx_obfuscator.py -i file1.py file2.py file3.py -o dist/ -m 2 --compile y -w 4

  3. Chạy CLI toàn bộ thư mục (đệ quy):
     python tr0ngx_obfuscator.py -d src/ -o dist/ -r -m 2 --compile y --matrix y

  4. Chạy giao diện tương tác TUI (hỗ trợ chọn 1 file hoặc hàng loạt):
     python tr0ngx_obfuscator.py
        """
    )
    # File & Batch options
    parser.add_argument("-i", "--input", nargs="*", help="Đường dẫn một hoặc nhiều file Python / pattern glob cần obfuscate", default=None)
    parser.add_argument("-D", "--dir", "--directory", help="Đường dẫn thư mục chứa các file Python cần obfuscate hàng loạt", default=None)
    parser.add_argument("-r", "--recursive", action="store_true", help="Quét đệ quy tất cả thư mục con khi obfuscate thư mục")
    parser.add_argument("-o", "--output", help="Đường dẫn file kết quả (nếu 1 file) hoặc thư mục kết quả (nếu nhiều file)", default=None)
    parser.add_argument("-w", "--workers", "--jobs", "-j", type=int, default=None, help="Số luồng CPU xử lý song song khi obfuscate nhiều file")
    
    # Engine modes
    parser.add_argument("-m", "--mode", type=int, choices=[1, 2, 3], help="Cấp độ làm rối Trongdepzai AST (1: Cơ bản, 2: Nâng cao, 3: Cực đại)", default=None)
    parser.add_argument("--moreobf", choices=["y", "n", "Y", "N"], help="Bơm mã rác AST junk & try-except dead code (y/n)", default=None)
    parser.add_argument("--antidebug", choices=["y", "n", "Y", "N"], help="Kích hoạt khiên chống debug & anti-hook (y/n)", default=None)
    parser.add_argument("--antivm", choices=["y", "n", "Y", "N"], help="Kích hoạt khiên phát hiện máy ảo (Anti-VM & Sandbox Detection) (y/n)", default=None)
    parser.add_argument("--selfmod", choices=["y", "n", "Y", "N"], help="Thêm tầng mã tự biến đổi chữ ký khi chạy (y/n)", default=None)
    parser.add_argument("--compile", choices=["y", "n", "Y", "N"], help="Biên dịch bytecode đa tầng (marshal + XOR + zlib + bz2) (y/n)", default=None)
    
    # Cryptographic Authentication & Passwords
    parser.add_argument("--password", type=str, default=None, help="Mật khẩu mã hóa payload chuẩn Argon2id + ChaCha20Poly1305 AEAD")
    parser.add_argument("--password-file", type=str, default=None, help="Đường dẫn file chứa mật khẩu mã hóa (tránh lộ password qua tiến trình)")
    parser.add_argument("--max-output-size", default=None, help="Giới hạn dung lượng file output tối đa (vd: 10MB, 50MB, 10485760)")
    parser.add_argument("--seed", type=int, default=None, help="Seed số nguyên để sinh mã định danh mang tính tái lập (Reproducible deterministic build)")

    # Velimatix engine
    parser.add_argument("--velimatix", choices=["y", "n", "Y", "N"], help="Kích hoạt động cơ Velimatix AST (y/n)", default=None)
    parser.add_argument("--veli-level", type=int, choices=[1, 2, 3], help="Cấp độ Velimatix (1: BiOpaque, 2: Exception Jump, 3: Match-Case State Machine)", default=None)
    parser.add_argument("--double-compile", choices=["y", "n", "Y", "N"], help="Đóng gói kép (Trongdepzai bytecode bên trong loader Velimatix) (y/n)", default=None)
    
    # Outer layers & variables
    parser.add_argument("--kramer", choices=["y", "n", "Y", "N"], help="Bọc ngoài bằng khiên Kramer Kyrie Eleison (y/n)", default=None)
    parser.add_argument("--cjk-vars", choices=["y", "n", "Y", "N"], help="Sử dụng biến ký tự chữ Hán / CJK & docstring PyCool (y/n)", default=None)
    parser.add_argument("--force-py", help="Khóa chỉ cho phép chạy trên phiên bản Python chỉ định (vd: 3.10, 3.11, 3.12, 3.14) hoặc 'off'", default=None)
    
    # Debug & Environment controls
    parser.add_argument("--debug-map", nargs="?", const="AUTO", default=None, help="Xuất bản đồ ánh xạ ký hiệu & thời gian từng stage ra file JSON (vd: --debug-map map.json)")
    parser.add_argument("--debug", "-d", action="store_true", help="Bật chế độ debug chi tiết (in log micro-stages, traceback và cảnh báo lỗi)")
    parser.add_argument("--profile", action="store_true", help="Hiển thị bảng phân tích chi tiết hiệu năng (Profiling Waterfall & Bottleneck Analysis)")
    parser.add_argument("--log-file", type=str, default=None, help="Ghi toàn bộ log và chẩn đoán chi tiết ra file riêng (vd: --log-file debug.log)")
    parser.add_argument("--strict", action="store_true", help="Dừng tiến trình ngay khi gặp lỗi ở bất kỳ stage nào thay vì âm thầm bỏ qua")
    parser.add_argument("--no-art", "--quiet", "-q", action="store_true", help="Tắt banner ASCII art và hiệu ứng màu để chạy sạch trong CLI/Agent")
    
    # Resource limiting (RAM & CPU Cores)
    parser.add_argument("--max-ram", "--ram-limit", type=int, default=None, help="Giới hạn dung lượng RAM tối đa (MB) cho tiến trình (vd: --max-ram 2048)")
    parser.add_argument("--cores", "--threads", type=int, default=None, help="Giới hạn số CPU Cores/Threads sử dụng (vd: --cores 2)")

    # New obfuscation modes
    parser.add_argument("--matrix", "--fused", choices=["y", "n", "Y", "N"], help="Kich hoat Ma Tran Hoa Quyen Da Tang (Hybrid Blended Variables + Fused 3-Track Shield) (y/n)", default=None)
    parser.add_argument("--emoji-obf", choices=["y", "n", "Y", "N"], help="Ma hoa output thanh chuoi emoji sequence (y/n)", default=None)
    parser.add_argument("--homoglyph", choices=["y", "n", "Y", "N"], help="Dung ten bien Cyrillic/Greek trong giong ASCII (a->а, o->о) (y/n)", default=None)
    parser.add_argument("--rare-unicode", choices=["y", "n", "Y", "N"], help="Dung ky tu Unicode sieu hiem (CJK Extension B, Kangxi) (y/n)", default=None)
    parser.add_argument("--zalgo", "--combining-marks", "-z", choices=["y", "n", "Y", "N"], help="Kich hoat khien Zalgo Combining Marks chong cuc nhieu dau lam lag engine render GUI/Decompiler (y/n)", default=None)
    parser.add_argument("--whitespace-obf", choices=["y", "n", "Y", "N"], help="Mã hóa output thành khoảng trắng vô hình (space=0, tab=1) (y/n)", default=None)
    parser.add_argument("--blank-padding", "--blank-lines", choices=["y", "n", "Y", "N"], help="Chèn hàng trăm dòng khoảng trống trắng tinh ở đầu file (Screen Blanker Padding) (y/n)", default=None)
    parser.add_argument("--hyperion", choices=["y", "n", "Y", "N"], help="Kích hoạt Hyperion Engine (Builtins remapping + token variable remapping + math/str obfuscation + chunk shell) (y/n)", default=None)
    parser.add_argument("--camouflage", "--camo", choices=["y", "n", "Y", "N"], help="Kích hoạt lớp ngụy trang Hyperion Camouflage (Fake Scientific/Algorithmic Class simulation) (y/n)", default=None)
    parser.add_argument("--math-opaque", choices=["y", "n", "Y", "N"], help="Kích hoạt vị từ toán học mờ (Mathematical Opaque Predicates - Quadratic Non-Residue mod 7 & Euler invariants) (y/n)", default=None)
    parser.add_argument("--dyn-strings", choices=["y", "n", "Y", "N"], help="Mã hóa chuỗi động XOR cục bộ từng vị trí gọi (Per-callsite dynamic XOR string encryption) (y/n)", default=None)
    parser.add_argument("--anti-dump", choices=["y", "n", "Y", "N"], help="Kích hoạt khiên chống memory dump & lọc đối tượng GC (In-Memory Anti-Dump & GC Object Scrubber) (y/n)", default=None)
    parser.add_argument("--vm-obf", choices=["y", "n", "Y", "N"], help="Kích hoạt VM Virtualization Engine - biến đổi code thành bytecode ảo thực thi bởi CPU ảo đa hình (y/n)", default=None)
    parser.add_argument("--vm-level", type=int, choices=[1, 2, 3, 4], help="Cấp độ VM Virtualization (1: Basic, 2: + Traps/NOP, 3: + Dummy/Scrub, 4: + Per-Function ISA Keys)", default=None)
    parser.add_argument("--dec-trap", "--dectrap", choices=["y", "n", "Y", "N"], help="Kích hoạt bẫy điều khiển luồng Decompiler Traps (làm sập uncompyle6, decompyle3, pycdc) (y/n)", default=None)
    parser.add_argument("--var-split", choices=["y", "n", "Y", "N"], help="Phân rã biến số nguyên thành các mảnh bí mật XOR (Variable Secret Sharing) (y/n)", default=None)
    parser.add_argument("--str-frag", choices=["y", "n", "Y", "N"], help="Băm nhỏ chuỗi và nạp mồi nhử trong const pool (String Fragmentation & Decoy Pool) (y/n)", default=None)
    parser.add_argument("--debug-poison", choices=["y", "n", "Y", "N"], help="Kích hoạt trạng thái nhiễm độc ngầm Deceptive Debug Poisoning State Machine (y/n)", default=None)
    parser.add_argument("--spoof-meta", choices=["y", "n", "Y", "N"], help="Ngụy trang siêu dữ liệu và đường dẫn module stdlib (Metadata & co_filename Spoofing) (y/n)", default=None)
    parser.add_argument("--exotic-pools", choices=["y", "n", "Y", "N"], help="Identifier từ các pool Unicode cực hiếm (Tangut, Egyptian Hieroglyphs, CJK Ext G/H, Anatolian, Bamum, Glagolitic, Miao) - XID + NFKC validated (y/n)", default=None)
    parser.add_argument("--base4096", choices=["y", "n", "Y", "N"], help="Encode payload thanh stream glyph 12-bit tu block Unicode hiem (Base4096 exotic alphabet) (y/n)", default=None)
    parser.add_argument("--bit-matrix", choices=["y", "n", "Y", "N"], help="Bien doi byte da vong: LCG-XOR / bit rotation / nibble swap / S-Box permutation (y/n)", default=None)
    parser.add_argument("--lzma-layer", choices=["y", "n", "Y", "N"], help="Them lop nen LZMA (preset 9) truoc ma hoa AEAD - giam 10-25%% kich thuoc payload (y/n)", default=None)
    parser.add_argument("--env-key", choices=["y", "n", "Y", "N"], help="Khoa payload theo fingerprint phan cung (MAC/host/arch) - che do khong mat khau; sai may = that bai xac thuc (y/n)", default=None)
    parser.add_argument("--verify", choices=["y", "n", "Y", "N", "off"], help="Post-build semantic differential: runs original vs obfuscated output and compares stdout + exit codes (y/n)", default=None)
    parser.add_argument("--shared-symbols", choices=["y", "n", "Y", "N"], help="Batch mode: two-phase cross-module symbol sync with frozen deterministic rename map (y/n)", default=None)
    parser.add_argument("--vm-annotations", choices=["y", "n", "Y", "N"], help="Preserve type annotations in VM bytecode: enables dataclasses/pydantic/FastAPI under virtualization. Default off to reduce size (y/n)", default=None)
    parser.add_argument("--anti-intercept", choices=["y", "n", "Y", "N"], help="Deep Anti-Read Shield: 5-layer network/memory/introspection protection - module import block, socket encrypted I/O, SSL CA pinning, GC scrub, process watchdog (y/n)", default=None)

    cli_args, unknown = parser.parse_known_args()
    if unknown:
        for _u in unknown:
            if not str(_u).startswith("-"):
                continue
            print(f"[-] ERROR: unrecognized argument: {_u}", file=sys.stderr)
        sys.exit(2)
    is_cli_mode = bool(cli_args.input is not None or cli_args.dir is not None)

    if getattr(cli_args, 'debug', False):
        _trx_cfg._EngineState.verbose_debug = True
    if getattr(cli_args, 'profile', False):
        _trx_cfg._EngineState.profile_mode = True
    if getattr(cli_args, 'strict', False):
        _trx_cfg._EngineState.strict_mode = True
    if getattr(cli_args, 'log_file', None):
        _trx_cfg._EngineState.log_file_path = cli_args.log_file.strip().strip('"').strip("'")

    if cli_args.no_art or is_cli_mode:
        _trx_cfg._EngineState.cli_quiet_mode = True

    targets = []
    is_batch = False
    custom_out = cli_args.output

    _setup = None
    if is_cli_mode:
        targets = _resolve_input_files(inputs=cli_args.input, directory=cli_args.dir, recursive=cli_args.recursive)
        if not targets:
            _v(" [ERROR] CLI: Không tìm thấy bất kỳ file Python (.py) hợp lệ nào.")
            sys.exit(1)
        if len(targets) > 1 or cli_args.dir is not None:
            is_batch = True
    else:
        # Interactive TUI layer lives in tui.py. Lazy import: tui statically
        # imports _resolve_input_files from this module, so this edge stays
        # call-time only to keep the package graph acyclic.
        from .tui import (
            run_interactive,
            prompt_feature_flags,
            ask_force_python,
            ask_build_extras,
            ask_encryption_password,
        )
        targets, is_batch, custom_out, _setup = run_interactive(cli_args)

    # Resource capping and workers
    max_ram = cli_args.max_ram
    max_cores = cli_args.cores
    # FIX (audit P1): -w 0 previously fell through the falsy-or chain to auto;
    # zero is now rejected exactly like negative values.
    if cli_args.workers is not None and cli_args.workers < 1:
        print(f"[-] ERROR: --workers must be a positive integer (got: {cli_args.workers}).", file=sys.stderr)
        sys.exit(2)
    workers = cli_args.workers or max_cores or max(2, min(8, (os.cpu_count() or 4)))
    if not isinstance(workers, int) or workers < 1:
        print(f"[-] ERROR: --workers must be a positive integer (got: {workers}).", file=sys.stderr)
        sys.exit(2)

    # In-memory scrubbing: overwrite sensitive password in sys.argv to prevent procfs inspection
    for idx, arg in enumerate(sys.argv):
        if arg == '--password' and idx + 1 < len(sys.argv):
            sys.argv[idx + 1] = '*' * len(sys.argv[idx + 1])
        elif arg.startswith('--password='):
            sys.argv[idx] = '--password=' + ('*' * (len(arg) - 11))

    # 2. Mode
    if cli_args.mode is not None:
        mode = cli_args.mode
    else:
        while True:
            try:
                mode = int(_prompt_input(" ENTER MODE (1-3): "))
                if 1 <= mode <= 3:
                    break
                _v(" ENTER 1, 2, OR 3")
            except ValueError:
                _v(" INVALID INPUT")

    # 3. Flags (interactive arms resolved by tui.prompt_feature_flags)
    _tui_flags = None
    if not is_cli_mode:
        _tui_flags = prompt_feature_flags(cli_args)

    moreobf = cli_args.moreobf or ("N" if is_cli_mode else _tui_flags["moreobf"])
    antidebug = cli_args.antidebug or ("N" if is_cli_mode else _tui_flags["antidebug"])
    antivm = getattr(cli_args, 'antivm', None) or ("N" if is_cli_mode else _tui_flags["antivm"])
    selfmodify = cli_args.selfmod or ("N" if is_cli_mode else _tui_flags["selfmodify"])
    method = cli_args.compile or ("N" if is_cli_mode else _tui_flags["method"])
    velimatix = cli_args.velimatix or ("N" if is_cli_mode else _tui_flags["velimatix"])

    veli_level = 1
    if velimatix.upper() == "Y":
        if cli_args.veli_level is not None:
            veli_level = cli_args.veli_level
        else:
            if is_cli_mode:
                veli_level = 3
            else:
                veli_level = _tui_flags["veli_level"]

    double_compile = "N"
    if method.upper() == "Y" and velimatix.upper() == "Y":
        double_compile = cli_args.double_compile or ("Y" if is_cli_mode else _tui_flags["double_compile"])

    kramer_wrap_choice = cli_args.kramer or ("N" if is_cli_mode else _tui_flags["kramer"])
    cjk_choice = cli_args.cjk_vars or ("N" if is_cli_mode else _tui_flags["cjk"])

    # New Obfuscation Modes
    matrix_choice = cli_args.matrix or ("N" if is_cli_mode else _tui_flags["matrix"])
    emoji_obf_choice = cli_args.emoji_obf or ("N" if is_cli_mode else _tui_flags["emoji_obf"])
    homoglyph_choice = cli_args.homoglyph or ("N" if is_cli_mode else _tui_flags["homoglyph"])
    rare_unicode_choice = cli_args.rare_unicode or ("N" if is_cli_mode else _tui_flags["rare_unicode"])
    zalgo_choice = getattr(cli_args, 'zalgo', None) or ("N" if is_cli_mode else _tui_flags["zalgo"])
    whitespace_obf_choice = cli_args.whitespace_obf or ("N" if is_cli_mode else _tui_flags["whitespace_obf"])
    blank_padding_choice = getattr(cli_args, 'blank_padding', None) or getattr(cli_args, 'blank_lines', None) or ("N" if is_cli_mode else _tui_flags["blank_padding"])
    hyperion_choice = getattr(cli_args, 'hyperion', None) or ("N" if is_cli_mode else _tui_flags["hyperion"])
    camouflage_choice = getattr(cli_args, 'camouflage', None) or ("N" if is_cli_mode else _tui_flags["camouflage"])
    math_opaque_choice = getattr(cli_args, 'math_opaque', None) or ("N" if is_cli_mode else _tui_flags["math_opaque"])
    dyn_strings_choice = getattr(cli_args, 'dyn_strings', None) or ("N" if is_cli_mode else _tui_flags["dyn_strings"])
    antidump_choice = getattr(cli_args, 'anti_dump', None) or ("N" if is_cli_mode else _tui_flags["anti_dump"])
    vm_obf_choice = getattr(cli_args, 'vm_obf', None) or ("N" if is_cli_mode else _tui_flags["vm_obf"])
    vm_level_choice = getattr(cli_args, 'vm_level', None) or 1
    dectrap_choice = getattr(cli_args, 'dec_trap', None) or getattr(cli_args, 'dectrap', None) or ("N" if is_cli_mode else _tui_flags["dec_trap"])
    varsplit_choice = getattr(cli_args, 'var_split', None) or ("N" if is_cli_mode else _tui_flags["var_split"])
    strfrag_choice = getattr(cli_args, 'str_frag', None) or ("N" if is_cli_mode else _tui_flags["str_frag"])
    debugpoison_choice = getattr(cli_args, 'debug_poison', None) or ("N" if is_cli_mode else _tui_flags["debug_poison"])
    spoofmeta_choice = getattr(cli_args, 'spoof_meta', None) or ("N" if is_cli_mode else _tui_flags["spoof_meta"])
    exotic_pools_choice = getattr(cli_args, 'exotic_pools', None) or ("N" if is_cli_mode else _tui_flags["exotic_pools"])
    base4096_choice = getattr(cli_args, 'base4096', None) or ("N" if is_cli_mode else _tui_flags["base4096"])
    bit_matrix_choice = getattr(cli_args, 'bit_matrix', None) or ("N" if is_cli_mode else _tui_flags["bit_matrix"])
    lzma_layer_choice = getattr(cli_args, 'lzma_layer', None) or "N"
    env_key_choice = getattr(cli_args, 'env_key', None) or "N"
    verify_mode_choice = getattr(cli_args, 'verify', None) or "N"
    _trx_cfg._EngineState.lzma_layer = lzma_layer_choice.upper() == "Y"
    _trx_cfg._EngineState.env_key_lock = env_key_choice.upper() == "Y"
    _trx_cfg._EngineState.verify_mode = verify_mode_choice.upper() == "Y"
    vm_annotations_choice = getattr(cli_args, 'vm_annotations', None) or "N"
    anti_intercept_choice = getattr(cli_args, 'anti_intercept', None) or "N"
    _trx_cfg._EngineState.vm_annotations = vm_annotations_choice.upper() == "Y"
    _trx_cfg._EngineState.anti_intercept = anti_intercept_choice.upper() == "Y"

    # Force Python version
    if cli_args.force_py is not None:
        if cli_args.force_py.lower() in ["n", "no", "off", "none"]:
            force_py_choice = "N"
            forced_py_ver = ""
        else:
            # FIX (audit P1): invalid versions like 'banana' previously passed
            # through and made every runtime guard vacuously true.
            # PERF G3: also accept a floor range like '3.12+' so artifacts can
            # target newer, faster interpreters instead of one pinned version.
            import re as _re_fp
            _fp_val = cli_args.force_py.strip()
            _fp_plus = _fp_val.endswith('+')
            if _fp_plus:
                _fp_val = _fp_val[:-1].strip()
            if not _re_fp.fullmatch(r"\d+\.\d+(\.\d+)?", _fp_val):
                print(f"[-] ERROR: --force-py expects a version like 3.10 / 3.11.4 or a floor like 3.12+ (got: {cli_args.force_py!r}).", file=sys.stderr)
                sys.exit(2)
            force_py_choice = "Y"
            forced_py_ver = _fp_val + ('+' if _fp_plus else '')
    else:
        if is_cli_mode:
            force_py_choice = "N"
            forced_py_ver = ""
        else:
            force_py_choice, forced_py_ver = ask_force_python()

    # Debug Map
    debug_map_arg = cli_args.debug_map
    if not is_cli_mode:
        debug_map_arg, max_ram, max_cores, custom_out = ask_build_extras(
            _setup, is_batch, debug_map_arg, max_ram, max_cores, custom_out
        )

    # Password resolution
    password = cli_args.password
    if cli_args.password_file:
        if not os.path.isfile(cli_args.password_file):
            print(f"[-] ERROR: --password-file not found: {cli_args.password_file}", file=sys.stderr)
            sys.exit(2)
        try:
            with open(cli_args.password_file, "r", encoding="utf-8") as pf:
                password = pf.read().strip()
        except Exception as e:
            print(f"[-] ERROR: cannot read --password-file: {e}", file=sys.stderr)
            sys.exit(2)
        if not password:
            print("[-] ERROR: --password-file is empty.", file=sys.stderr)
            sys.exit(2)
    if not password and os.environ.get("TR0NGX_PASSWORD"):
        password = os.environ.get("TR0NGX_PASSWORD")
    if not password and not is_cli_mode and method.upper() == "Y" and _setup != "1":
        pwd_inp = ask_encryption_password()
        if pwd_inp:
            password = pwd_inp
    _trx_cfg._EngineState.encryption_password = password
    if _trx_cfg._EngineState.env_key_lock and password:
        # Mutually exclusive trust roots: password = portable secret, env-key =
        # machine-bound. Combining them silently would weaken the documented
        # semantics of both; prefer the stronger portable mode.
        print("[TR0NGX] [WARN] --env-key is incompatible with --password; hardware lock disabled.", flush=True)
        _trx_cfg._EngineState.env_key_lock = False

    if cli_args.seed is not None:
        _trx_cfg._EngineState.custom_seed = cli_args.seed
        random.seed(cli_args.seed)

    max_output_size_bytes = _parse_size_str(cli_args.max_output_size)
    _trx_cfg._EngineState.max_output_size = max_output_size_bytes

    _apply_resource_limits(max_ram, max_cores)

    return {
        "targets": targets,
        "is_batch": is_batch,
        "mode": mode,
        "moreobf": moreobf,
        "antidebug": antidebug,
        "antivm": antivm,
        "selfmodify": selfmodify,
        "method": method,
        "password": password,
        "seed": cli_args.seed,
        "max_output_size": max_output_size_bytes,
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
        "vm_level": vm_level_choice,
        "dec_trap": dectrap_choice,
        "var_split": varsplit_choice,
        "str_frag": strfrag_choice,
        "debug_poison": debugpoison_choice,
        "spoof_meta": spoofmeta_choice,
        "exotic_pools": exotic_pools_choice,
        "base4096": base4096_choice,
        "bit_matrix": bit_matrix_choice,
        "lzma_layer": lzma_layer_choice,
        "env_key": env_key_choice,
        "verify": verify_mode_choice,
        "shared_symbols": getattr(cli_args, 'shared_symbols', None) or "N",
        "force_py_choice": force_py_choice,
        "forced_py_ver": forced_py_ver,
        "debug_map": debug_map_arg,
        "max_ram": max_ram,
        "max_cores": max_cores,
        "workers": workers,
        "custom_out": custom_out
    }

def _reset_global_state():
    """Reset global state between runs."""
    global _used_names, _DEBUG_MAP, _LOG_ENTRIES, _STAGE_ERRORS
    with _used_names_lock:
        _used_names.clear()
    _RareChars.pool = None
    BiOpaqueUtils.possible_args = []
    BiOpaqueUtils.possible_functions = []
    BiOpaqueUtils.alphabet = ""
    BiOpaqueUtils.length = 16
    BiOpaqueUtils.safe_mode = False
    MutatorUtils.alphabet = ""
    MutatorUtils.length = 16
    ExceptionJumpUtils.alphabet = ""
    ExceptionJumpUtils.length = 16
    ControlFlowUtils.alphabet = ""
    ControlFlowUtils.length = 16
    _trx_cfg._EngineState.use_cjk_names = False
    _trx_cfg._EngineState.use_homoglyph_names = False
    _trx_cfg._EngineState.use_rare_unicode_names = False
    _trx_cfg._EngineState.use_zalgo_marks = False
    _trx_cfg._EngineState.use_hyperion = False
    _trx_cfg._EngineState.use_camouflage = False
    _trx_cfg._EngineState.use_fused_names = False
    _trx_cfg._EngineState.use_exotic_pools = None
    _LOG_ENTRIES.clear()
    _STAGE_ERRORS.clear()
    _DEBUG_MAP["renamed_functions"].clear()
    _DEBUG_MAP["renamed_builtins"].clear()
    _DEBUG_MAP["renamed_variables"].clear()
    _DEBUG_MAP["stages"].clear()
    _DEBUG_MAP["errors"].clear()

_trx_cfg._EngineState.use_fused_names = False
_trx_cfg._EngineState.use_exotic_pools = None

_PYVER_TAG = f"{sys.version_info.major}.{sys.version_info.minor}"


# ======================================================================
# (slice gap filler)
# ======================================================================

def main():
    # ═══════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════
    # MAIN EXECUTION (CLI + TUI DISPATCHER)
    # ═══════════════════════════════════════════════════════════════
    _reset_global_state()
    _show_banner()
    _opts = get_args_or_prompt()
    targets = _opts["targets"]
    is_batch = _opts["is_batch"]
    custom_out = _opts["custom_out"]

    matrix_choice = _opts.get("matrix", "N")
    homoglyph_choice = _opts.get("homoglyph", "N")
    rare_unicode_choice = _opts.get("rare_unicode", "N")
    cjk_choice = _opts.get("cjk", "N")
    zalgo_choice = _opts.get("zalgo", "N")
    hyperion_choice = _opts.get("hyperion", "N")
    camouflage_choice = _opts.get("camouflage", "N")

    # Set name generation mode flags & Matrix fusion
    if matrix_choice.upper() == "Y" or (homoglyph_choice.upper() == "Y" and rare_unicode_choice.upper() == "Y"):
        _trx_cfg._EngineState.use_fused_names = True
        _init_rare_chars()
        _init_combining_marks()
    if cjk_choice.upper() == "Y":
        _trx_cfg._EngineState.use_cjk_names = True
    if homoglyph_choice.upper() == "Y":
        _trx_cfg._EngineState.use_homoglyph_names = True
    if rare_unicode_choice.upper() == "Y":
        _trx_cfg._EngineState.use_rare_unicode_names = True
        _init_rare_chars()
    if _opts.get("exotic_pools", "N").upper() == "Y":
        _trx_cfg._EngineState.use_exotic_pools = True
    if zalgo_choice.upper() == "Y":
        _trx_cfg._EngineState.use_zalgo_marks = True
        _init_combining_marks()
    if hyperion_choice.upper() == "Y":
        _trx_cfg._EngineState.use_hyperion = True
    if camouflage_choice.upper() == "Y":
        _trx_cfg._EngineState.use_camouflage = True

    _refresh_runtime_symbols()

    # Dispatch to batch runner if multiple files, or single file pipeline if 1 file
    if is_batch or len(targets) > 1:
        run_batch_obfuscation(targets, custom_out, _opts)
    else:
        src_target = targets[0]["src"]
        if custom_out:
            if os.path.isdir(custom_out) or custom_out.endswith("/") or custom_out.endswith("\\"):
                os.makedirs(custom_out, exist_ok=True)
                out_target = os.path.join(custom_out, os.path.basename(src_target))
            else:
                out_target = custom_out.strip().strip('"').strip("'")
        else:
            _dir_n, _base_n = os.path.split(src_target)
            out_target = os.path.join(_dir_n, "tr0ngx-" + _base_n) if _dir_n else ("tr0ngx-" + _base_n)

        _v(" ═══ STARTING OBFUSCATION ═══")
        res = obfuscate_single_target(src_target, out_target, _opts, quiet_progress=False)
        if not res["success"]:
            _v(f" [ERROR] Obfuscation failed: {res['error']}")
            if _trx_cfg._EngineState.strict_mode:
                sys.exit(1)
            return

        original_size = res["original_size"]
        file_size = res["output_size"]
        ratio = res["ratio"]
        elapsed = res["elapsed"]
        output_file = res["out"]

        _new_modes = []
        multi_shield_count = sum(1 for c in [_opts.get("kramer","N"), _opts.get("emoji_obf","N"), _opts.get("whitespace_obf","N")] if c.upper() == "Y")
        if (matrix_choice.upper() == "Y") or (multi_shield_count >= 2):
            _new_modes.append("MATRIX-FUSED (3-Track Symbiotic)")
        else:
            if _opts.get("emoji_obf", "N").upper() == "Y": _new_modes.append("EMOJI")
            if _opts.get("whitespace_obf", "N").upper() == "Y": _new_modes.append("WHITESPACE")
        if _trx_cfg._EngineState.use_fused_names:
            _new_modes.append("HYBRID-VARS")
        else:
            if homoglyph_choice.upper() == "Y": _new_modes.append("HOMOGLYPH")
            if rare_unicode_choice.upper() == "Y": _new_modes.append("RARE-UNI")
            if zalgo_choice.upper() == "Y": _new_modes.append("ZALGO-MARKS (Z͑͗͑͗... Diacritics)")
        if hyperion_choice.upper() == "Y": _new_modes.append("HYPERION-ENGINE")
        if camouflage_choice.upper() == "Y": _new_modes.append("HYPERION-CAMOUFLAGE")
        if _opts.get("math_opaque", "N").upper() == "Y": _new_modes.append("MATH-OPAQUE (Quadratic/Euler Invariants)")
        if _opts.get("dyn_strings", "N").upper() == "Y": _new_modes.append("DYN-STRINGS (Per-Callsite XOR)")
        if _opts.get("anti_dump", "N").upper() == "Y": _new_modes.append("ANTI-DUMP (GC Scrubber)")

        _veli_suffix = f"(L{_opts.get('veli_level', 1)})" if _opts['velimatix'].upper() == 'Y' else ""
        _summary_lines = [
            f"File Saved   : {output_file}",
            f"Original Size: {original_size:,} bytes",
            f"Output Size  : {file_size:,} bytes ({ratio:.1f}x)",
            f"Time Taken   : {elapsed:.2f}s",
            f"Mode         : {_opts['mode']} | Veli: {_opts['velimatix'].upper()}{_veli_suffix}",
            f"Compile      : {_opts['method'].upper()} | Double: {_opts['double_compile'].upper() if _opts['method'].upper()=='Y' else 'N'}",
            f"Protections  : Anti-Debug={_opts['antidebug'].upper()} | Anti-VM={_opts['antivm'].upper()} | Anti-Dump={_opts['anti_dump'].upper()} | Self-Mod={_opts['selfmodify'].upper()} | Kramer={_opts['kramer'].upper()}"
        ]
        if _new_modes:
            _summary_lines.append(f"Layers       : {' + '.join(_new_modes)}")

        _summary_text = "\n".join(_summary_lines)

        _v(_gradient_text(" ═══════════════════════════════════════", (85, 130, 255), (190, 85, 255)))
        if _trx_cfg._EngineState.cli_quiet_mode:
            _v(_summary_text)
        else:
            try:
                _boxed = Box.DoubleCube(_summary_text)
                _raw_print(Colorate.Diagonal(Colors.StaticMIX((Col.cyan, Col.purple)), _boxed))
            except Exception:
                _v(_summary_text)
        _v(_gradient_text(" ═══════════════════════════════════════", (85, 130, 255), (190, 85, 255)))
        if _trx_cfg._EngineState.profile_mode or _trx_cfg._EngineState.verbose_debug:
            _print_profile_waterfall(elapsed, original_size, file_size)
        _export_log_file()
        if _STAGE_ERRORS and not _trx_cfg._EngineState.strict_mode:
            failed_stages = ", ".join(sorted({e["stage"] for e in _STAGE_ERRORS}))
            _v(f" [!] WARNING: {len(_STAGE_ERRORS)} pipeline stage(s) FAILED: {failed_stages}")
            _v(" [!] Output was still written but may be MISSING protection layers listed above.")
        _v(" OBFUSCATION COMPLETE!")

if __name__ == "__main__":
    main()



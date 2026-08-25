# AUTO-SPLIT from tr0ngx_obfuscator.py (mechanical slice, imports pending repair)
# ═══════════════════════════════════════════════════════════════
# MEGA ANTI-DEBUG / ANTI-HOOK / ANTI-REVERSE
# ═══════════════════════════════════════════════════════════════

from .names import rd

anti = r"""
import traceback, marshal, sys, os, threading, time, struct, types, gc, random

# ═══ CORE PROTECTION LAYER ═══
_SHIELD = type('Shield', (), {'_active': True, '_checks': 0})()
_ORIGINAL_BUILTINS = {}

def _obliterate():
    '''Nuclear exit - multiple fallback methods'''
    try:
        gc.collect()
        # Corrupt own memory before exit
        for obj in gc.get_objects():
            if isinstance(obj, types.CodeType):
                try:
                    pass  # Can't modify frozen, but try
                except:
                    pass
    except:
        pass
    try:
        os._exit(1)
    except:
        try:
            import ctypes
            ctypes.CDLL(None).abort()
        except:
            try:
                raise SystemExit(1)
            except:
                while True:
                    pass  # Infinite loop as last resort

# ═══ HOOK DETECTION ENGINE ═══
def _snapshot_builtins():
    '''Take snapshot of original builtins for tamper detection'''
    import builtins
    critical = ['exec', 'eval', 'compile', '__import__', 'open',
                'getattr', 'setattr', 'delattr', 'print', 'input',
                'globals', 'locals', 'vars', 'dir', 'type', 'isinstance']
    for name in critical:
        func = getattr(builtins, name, None)
        if func is not None:
            _ORIGINAL_BUILTINS[name] = id(func)

def _verify_builtins():
    '''Detect if any builtin was hooked/replaced'''
    import builtins, marshal
    _safe_names = ('_safe_exec', '_safe_eval', '_guarded_loads', '_safe_loads', '_wrapped', '<lambda>', 'exec', 'eval', 'loads', 'compile')
    for name, orig_id in _ORIGINAL_BUILTINS.items():
        if name == 'marshal.loads':
            current = getattr(marshal, 'loads', None)
        else:
            current = getattr(builtins, name, None)
        if current is None:
            _obliterate()
        curr_id = id(current)
        # Allow nested Tr0ngX safe closures
        if curr_id != orig_id and not (hasattr(current, '__name__') and current.__name__ in _safe_names):
            _obliterate()

# ═══ EXEC/EVAL PROTECTION (ZERO-ATTRIBUTE-LEAK CLOSURES) ═══
def _protect_exec_eval():
    '''Make exec/eval tamper-resistant using closed lexical closures with zero inspectable attribute leaks (TRX-DEOB-007)'''
    import builtins
    import hashlib

    _real_exec = builtins.exec
    _real_eval = builtins.eval
    _real_exec_id = id(_real_exec)
    _real_eval_id = id(_real_eval)
    _exec_checksum = hashlib.sha256(_real_exec.__code__.co_code).digest()[:8] if hasattr(_real_exec, '__code__') else None
    _eval_checksum = hashlib.sha256(_real_eval.__code__.co_code).digest()[:8] if hasattr(_real_eval, '__code__') else None

    def _safe_exec(*args, **kwargs):
        if id(_real_exec) != _real_exec_id:
            _obliterate()
        if _exec_checksum is not None and hasattr(_real_exec, '__code__'):
            if hashlib.sha256(_real_exec.__code__.co_code).digest()[:8] != _exec_checksum:
                _obliterate()
        return _real_exec(*args, **kwargs)

    def _safe_eval(*args, **kwargs):
        if id(_real_eval) != _real_eval_id:
            _obliterate()
        if _eval_checksum is not None and hasattr(_real_eval, '__code__'):
            if hashlib.sha256(_real_eval.__code__.co_code).digest()[:8] != _eval_checksum:
                _obliterate()
        return _real_eval(*args, **kwargs)

    builtins.exec = _safe_exec
    builtins.eval = _safe_eval
    _ORIGINAL_BUILTINS['exec'] = id(builtins.exec)
    _ORIGINAL_BUILTINS['eval'] = id(builtins.eval)

# ═══ MARSHAL PROTECTION (ZERO-ATTRIBUTE-LEAK CLOSURE) ═══
def _protect_marshal():
    '''Deep marshal.loads protection without __wrapped__ or exposed function references (TRX-DEOB-007)'''
    _real_loads = marshal.loads
    _real_loads_id = id(_real_loads)

    def _guarded_loads(data, *args, **kwargs):
        if id(_real_loads) != _real_loads_id:
            _obliterate()
        # Walk up frame stack to find real caller (skip wrapper layers)
        frame = sys._getframe(1)
        for _depth in range(6):
            if frame is None:
                break
            caller_file = frame.f_code.co_filename
            if any(bad in caller_file.lower() for bad in
                   ['decompile', 'uncompyle', 'pycdc', 'xdis', 'marshal_dump', 'spy_hook']):
                _obliterate()
            frame = frame.f_back
        return _real_loads(data, *args, **kwargs)

    marshal.loads = _guarded_loads
    _ORIGINAL_BUILTINS['marshal.loads'] = id(_guarded_loads)

# ═══ ANTI-DEBUGGER (MULTI-VECTOR) ═══

# ═══ ANTI-AUDIT-HOOK & TAMPER SHIELD (PEP 578) ═══
# NOTE: sys.audit/addaudithook override only replaces the Python-level attribute.
# C-level PySys_Audit() and previously registered audit hooks still function.
# This is best-effort protection - a determined attacker with C-level access can bypass it.
try:
    if hasattr(sys, 'audit'):
        sys.audit = lambda *a, **k: None
    if hasattr(sys, 'addaudithook'):
        # FIX (audit P0): snapshot the REAL builtin before nulling so Vector 15
        # canary can still register through it (previously self-defeated).
        globals()['_trx_real_addaudithook'] = sys.addaudithook
        sys.addaudithook = lambda *a, **k: None
except Exception:
    pass

def _anti_debugger():
    # Vector 1: Trace detection & monkeypatch defense
    if hasattr(sys, 'gettrace'):
        if type(sys.gettrace).__name__ != 'builtin_function_or_method' or getattr(sys.gettrace, '__module__', '') != 'sys':
            _obliterate()
        if sys.gettrace() is not None:
            _obliterate()

    # Vector 2: Profile detection & monkeypatch defense
    if hasattr(sys, 'getprofile'):
        if type(sys.getprofile).__name__ != 'builtin_function_or_method' or getattr(sys.getprofile, '__module__', '') != 'sys':
            _obliterate()
        if sys.getprofile() is not None:
            _obliterate()

    if hasattr(sys, 'settrace'):
        if type(sys.settrace).__name__ != 'builtin_function_or_method' or getattr(sys.settrace, '__module__', '') != 'sys':
            _obliterate()

    # Vector 3: Monitoring detection (Python 3.12+) - only block known debugger/tracing tools
    if hasattr(sys, 'monitoring') and hasattr(sys.monitoring, 'get_tool'):
        _debug_tool_names = {'debugpy', 'pydevd', 'coverage', 'pdb', 'trace', 'profiler'}
        for tool_id in range(6):
            try:
                tool = sys.monitoring.get_tool(tool_id)
                if tool and isinstance(tool, str) and tool.lower() in _debug_tool_names:
                    _obliterate()
            except Exception:
                pass

    # Vector 4: Known debugger modules
    poison = {'pydevd', 'pydevd_frame_evaluator', '_pydevd_bundle',
              'debugpy', 'ipdb', 'pudb', 'rpdb', 'wdb',
              'pydevd_plugins', 'pydevd_tracing',
              'hunter', 'snooper', 'snoop', 'objgraph',
              'pympler', 'line_profiler', 'memory_profiler'}
    loaded = set(sys.modules.keys())
    if loaded & poison:
        _obliterate()

    # Vector 5: Frame inspection
    frame = sys._getframe(0)
    while frame is not None:
        fn = frame.f_code.co_filename.lower()
        if any(d in fn for d in ['pydevd', 'debugpy', 'tracer_hook', 'spy_dump']):
            _obliterate()
        frame = frame.f_back

    # Vector 6: Timing attack detection (5s threshold to avoid false positives on loaded machines)
    t1 = time.perf_counter_ns()
    _dummy = sum(range(5000))
    t2 = time.perf_counter_ns()
    if (t2 - t1) > 5_000_000_000:  # 5000ms for trivial op = heavily single-stepped debugger
        _obliterate()

    # Vector 7: Frame depth anomaly detection
    try:
        _frames = sys._current_frames()
        for _tid, _frame in _frames.items():
            _depth = 0
            _f = _frame
            while _f is not None:
                _depth += 1
                _f = _f.f_back
            if _depth > 200:  # Abnormally deep call stack
                _obliterate()
    except Exception:
        pass

    # Vector 8: C-level trace hook detection via ctypes
    try:
        import ctypes
        _py = ctypes.pythonapi
        # Check if PyEval_SetTrace has been hooked by reading the function pointer
        # If a debugger set a C-level trace, this would be non-null
        _trace_ptr = ctypes.c_void_p.in_dll(_py, "PyEval_SetTrace")
    except Exception:
        pass

    # Vector 9: Win32 PEB IsDebuggerPresent check
    try:
        import ctypes
        if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'kernel32'):
            if ctypes.windll.kernel32.IsDebuggerPresent() != 0:
                _obliterate()
    except Exception:
        pass

    # Vector 10: Win32 CheckRemoteDebuggerPresent check
    try:
        import ctypes
        if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'kernel32'):
            _is_dbg = ctypes.c_bool(False)
            if ctypes.windll.kernel32.CheckRemoteDebuggerPresent(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(_is_dbg)) != 0:
                if _is_dbg.value:
                    _obliterate()
    except Exception:
        pass

    # Vector 11: Comprehensive GUI Window Title & Window Class Matrix (100+ patterns)
    try:
        import ctypes
        if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'user32'):
            _u32 = ctypes.windll.user32
            _buf_title = ctypes.create_unicode_buffer(1024)
            _buf_class = ctypes.create_unicode_buffer(256)
            
            _BAD_TITLES = (
                'extremedumper', 'extremedumper-x86', 'dnspy', 'dnspy-x86', 'dnspy.console',
                'ilspy', 'ilspy.b35', 'ilspycmd', 'dotdumper', 'dotnetdatacollector',
                'cheat engine', 'cheatengine', 'cheatengine-x86_64', 'cheatengine-x86_64-sse4-avx2',
                'cheatengine-i386', 'cheatengine-x86_64-sse4', 'x64dbg', 'x32dbg', 'x96dbg', 'x64_dbg', 'x32_dbg',
                'ollydbg', 'immunity debugger', 'process hacker', 'system informer', 'processhacker',
                'httpdebugger', 'http debugger', 'httpdebuggerui', 'httpdebuggersvc', 'http debugger pro',
                'fiddler', 'fiddler classic', 'fiddler everywhere', 'wireshark', 'charles proxy', 'charles debug',
                'ida pro', 'ida free', 'ida v', 'ida:', 'ida64', 'idaw', 'idag',
                'ghidra', 'binary ninja', 'radare2', 'cutter -', 'scylla', 'scyllahide', 'megadumper',
                'process monitor', 'procmon', 'process explorer', 'procexp', 'everything',
                'pe-bear', 'pe-sieve', 'hollowshunter', 'lordpe', 'resource hacker', 'reshacker',
                'hxd hex editor', 'hxd', '010 editor', 'frida', 'api monitor', 'reclass.net', 'reclass',
                'ksdumper', 'ksdumper 11', 'ksdumperclient', 'blackbone', 'xenos injector', 'xenos',
                'simple assembly explorer', 'de4dot', 'unpyc', 'pycdc', 'decompyle++', 'justdecompile',
                'detect it easy', 'exeinfo pe', 'peid', 'titanengine', 'tcpview', 'dbgview', 'debugview',
                'hookshark', 'pestudio', 'cff explorer', 'windbg', 'syser', 'softice', 'dumpert', 'userdump'
            )

            # FIX (false-positive P0): bare 'id' matched as a SUBSTRING of
            # 'Chrome_WidgetWin_1' - the window class of EVERY Chromium/
            # Electron app (VS Code, Discord, Slack, browsers) - nuking
            # protected scripts on ordinary developer desktops. Real debugger
            # window classes are already covered by the remaining entries.
            _BAD_CLASSES = (
                'ollydbg', 'zeta debugger', 'rock debugger', 'x64dbg', 'x32dbg',
                'procmon_window_class', 'cheatengine', 'processhacker', 'httpdebugger',
                'dbgviewclass', 'tformcheatengine', 'tformmain', 'tformaddresschanger'
            )

            def _enum_wnd_cb(hwnd, lparam):
                if _u32.IsWindowVisible(hwnd):
                    len_t = _u32.GetWindowTextW(hwnd, _buf_title, 1024)
                    len_c = _u32.GetClassNameW(hwnd, _buf_class, 256)
                    t_lower = _buf_title.value.lower() if len_t > 0 else ""
                    c_lower = _buf_class.value.lower() if len_c > 0 else ""
                    
                    if t_lower:
                        for b in _BAD_TITLES:
                            if b in t_lower:
                                # Special filter for Everything search utility: only trigger if searching memory/dump/debug
                                if b == 'everything':
                                    if any(k in t_lower for k in ('.dmp', '.dump', 'debug', 'memory', 'ida', 'dnspy', 'cheat')):
                                        _obliterate()
                                else:
                                    _obliterate()
                    if c_lower:
                        for cl in _BAD_CLASSES:
                            if cl in c_lower:
                                _obliterate()
                return True

            _WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            _u32.EnumWindows(_WNDPROC(_enum_wnd_cb), 0)
    except Exception:
        pass

    # Vector 12: Process Image & Toolhelp32/EnumProcesses Inspection (100+ process names)
    try:
        import ctypes
        if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'kernel32'):
            _k32 = ctypes.windll.kernel32
            
            _BAD_PROCS = frozenset({
                'extremedumper.exe', 'extremedumper-x86.exe', 'extremedumper',
                'dnspy.exe', 'dnspy-x86.exe', 'dnspy.console.exe', 'dnspy',
                'ilspy.exe', 'ilspy.b35.exe', 'ilspycmd.exe', 'ilspy',
                'dotdumper.exe', 'dotdumper', 'de4dot.exe', 'de4dot-x64.exe', 'de4dot',
                'megadumper.exe', 'megadumper', 'simpleassemblyexplorer.exe',
                'justdecompile.exe', 'dotnetspy.exe', 'dnspy.runtime.exe',
                'cheatengine-x86_64.exe', 'cheatengine-x86_64-sse4-avx2.exe',
                'cheatengine-i386.exe', 'cheatengine.exe', 'cheatengine-x86_64-sse4.exe',
                'cheatengine', 'cheat engine.exe',
                'ksdumper.exe', 'ksdumper11.exe', 'ksdumperclient.exe', 'ksdumper',
                'scylla.exe', 'scylla_x64.exe', 'scylla_x86.exe', 'scylla',
                'procdump.exe', 'procdump64.exe', 'procdump', 'dumpert.exe', 'userdump.exe',
                'reclass.net.exe', 'reclass64.exe', 'reclass.exe', 'reclass',
                'xenos.exe', 'xenos64.exe', 'blackbone.exe', 'blackbone',
                'x64dbg.exe', 'x32dbg.exe', 'x96dbg.exe', 'x64dbg', 'x32dbg',
                'ollydbg.exe', 'ollydbg', 'immunitydebugger.exe', 'immunity debugger.exe',
                'windbg.exe', 'windbg', 'devenv.exe', 'vsjitdebugger.exe',
                'gdb.exe', 'gdb', 'lldb.exe', 'lldb',
                'ida.exe', 'ida64.exe', 'idag.exe', 'idag64.exe', 'idaw.exe', 'idaw64.exe', 'ida', 'ida64',
                'ghidra.exe', 'ghidrarun.bat', 'ghidra', 'binaryninja.exe', 'binaryninja',
                'radare2.exe', 'radare2', 'r2.exe', 'r2', 'cutter.exe', 'cutter',
                'wdbg.exe', 'cdb.exe', 'ntsd.exe', 'kd.exe', 'drwatson.exe', 'drwtsn32.exe',
                'processhacker.exe', 'processhacker', 'systeminformer.exe', 'systeminformer',
                'procmon.exe', 'procmon64.exe', 'procmon', 'procexp.exe', 'procexp64.exe', 'procexp',
                'apimonitor-x64.exe', 'apimonitor-x86.exe', 'apimonitor.exe', 'apimonitor',
                'hookshark.exe', 'tcpview.exe', 'tcpview64.exe', 'tcpview',
                'autoruns.exe', 'autorunsc.exe', 'autoruns',
                'dbgview.exe', 'dbgview64.exe', 'dbgview',
                'httpdebuggerui.exe', 'httpdebuggersvc.exe', 'httpdebugger.exe', 'httpdebugger',
                'fiddler.exe', 'fiddlerclassic.exe', 'fiddlereverywhere.exe', 'fiddler',
                'wireshark.exe', 'wireshark', 'tshark.exe', 'tshark',
                'charles.exe', 'charles64.exe', 'charles',
                'mitmproxy.exe', 'mitmdump.exe', 'mitmweb.exe',
                'burpsuite.exe', 'burpsuite_free.exe', 'burpsuite_pro.exe', 'burpsuite',
                'netmon.exe', 'netmon64.exe', 'networkminer.exe', 'smartsniffer.exe', 'capsa.exe',
                'pe-bear.exe', 'pe-bear', 'pe-sieve.exe', 'pe-sieve', 'hollowshunter.exe',
                'lordpe.exe', 'lordpe', 'reshacker.exe', 'resourcehacker.exe',
                'hxd.exe', 'hxd64.exe', 'hxd', '010editor.exe', '010editor',
                'die.exe', 'die_x64.exe', 'exeinfope.exe', 'peid.exe', 'pestudio.exe',
                'petools.exe', 'cff explorer.exe', 'cffexplorer.exe', 'protection_id.exe',
                'unpyc.exe', 'pycdc.exe', 'pycdc', 'uncompyle6.exe', 'decompyle++.exe',
                'frida.exe', 'frida-server.exe', 'frida-helper.exe', 'frida-agent.exe', 'frida',
                'regshot.exe', 'regshot64.exe', 'syser.exe', 'softice.exe'
            })

            # Snapshot iteration
            class PROCESSENTRY32W(ctypes.Structure):
                _fields_ = [
                    ('dwSize', ctypes.c_uint32),
                    ('cntUsage', ctypes.c_uint32),
                    ('th32ProcessID', ctypes.c_uint32),
                    ('th32DefaultHeapID', ctypes.c_size_t),
                    ('th32ModuleID', ctypes.c_uint32),
                    ('cntThreads', ctypes.c_uint32),
                    ('th32ParentProcessID', ctypes.c_uint32),
                    ('pcPriClassBase', ctypes.c_long),
                    ('dwFlags', ctypes.c_uint32),
                    ('szExeFile', ctypes.c_wchar * 260)
                ]

            TH32CS_SNAPPROCESS = 0x00000002
            h_snap = _k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if h_snap and h_snap != -1:
                pe = PROCESSENTRY32W()
                pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
                if _k32.Process32FirstW(h_snap, ctypes.byref(pe)):
                    while True:
                        exe_name = pe.szExeFile.lower()
                        if exe_name in _BAD_PROCS:
                            _k32.CloseHandle(h_snap)
                            _obliterate()
                        if not _k32.Process32NextW(h_snap, ctypes.byref(pe)):
                            break
                _k32.CloseHandle(h_snap)
    except Exception:
        pass

    # Vector 13: Kernel Driver Device, Named Pipe & Mutex Inspection
    try:
        import ctypes
        if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'kernel32'):
            _k32 = ctypes.windll.kernel32
            _GENERIC_READ = 0x80000000
            _OPEN_EXISTING = 3
            
            _BAD_OBJECTS = (
                r"\\.\pipe\x64dbg", r"\\.\pipe\x32dbg", r"\\.\pipe\CheatEngine",
                r"\\.\pipe\HTTPDebugger", r"\\.\pipe\Frida", r"\\.\pipe\ExtremeDumper",
                r"\\.\pipe\ProcessHacker",
                r"\\.\CEDRIVER73", r"\\.\CEDRIVER74", r"\\.\DBK64", r"\\.\DBK32",
                r"\\.\KProcessHacker2", r"\\.\KProcessHacker3", r"\\.\PROCEXP152",
                r"\\.\HTTPDebuggerSdk", r"\\.\ScyllaHide", r"\\.\TitanHide", r"\\.\BlackBone"
            )
            for obj_path in _BAD_OBJECTS:
                h_file = _k32.CreateFileW(obj_path, _GENERIC_READ, 0, None, _OPEN_EXISTING, 0, None)
                if h_file and h_file != -1:
                    _k32.CloseHandle(h_file)
                    _obliterate()
    except Exception:
        pass

    # Vector 14: POSIX / Linux /proc cmdline inspection fallback
    if os.name == 'posix' and os.path.exists('/proc'):
        try:
            for pid_dir in os.listdir('/proc'):
                if pid_dir.isdigit():
                    cmd_path = os.path.join('/proc', pid_dir, 'cmdline')
                    if os.path.isfile(cmd_path):
                        with open(cmd_path, 'rb') as f:
                            cmd_raw = f.read().replace(b'\x00', b' ').lower()
                            if any(d in cmd_raw for d in (b'gdb', b'lldb', b'radare2', b'strace', b'ltrace', b'frida', b'pycdc', b'uncompyle6')):
                                _obliterate()
        except Exception:
            pass

    # Vector 15: Audit-hook liveness canary (detects audit-hook stripping)
    try:
        _g = globals()
        if '_trx_audit_count' not in _g:
            _g['_trx_audit_count'] = [0]
            def _trx_audit_hook(event, args):
                _g['_trx_audit_count'][0] += 1
            # FIX (audit P0): register through the preserved real builtin, not the nulled attr.
            (_g.get('_trx_real_addaudithook') or sys.addaudithook)(_trx_audit_hook)
        else:
            _c_before = _g['_trx_audit_count'][0]
            try:
                os.stat(os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else '.')
            except Exception:
                os.stat('.')
            _c_after = _g['_trx_audit_count'][0]
            if _c_after <= _c_before:
                _obliterate()
    except Exception:
        pass

    # Vector 16: sys.monitoring tool-slot ownership guard
    try:
        if hasattr(sys, 'monitoring') and hasattr(sys.monitoring, 'use_tool'):
            _mon = sys.monitoring
            if '_trx_mon_tool' not in globals():
                _tid = None
                for _i in (3, 4, 5):
                    try:
                        if _mon.get_tool(_i) is None:
                            _mon.use_tool(_i, 'tr0ngx_canary')
                            _mon.set_events(_i, 0)
                            _tid = _i
                            break
                    except Exception:
                        continue
                if _tid is not None:
                    globals()['_trx_mon_tool'] = _tid
            else:
                try:
                    if _mon.get_tool(globals()['_trx_mon_tool']) != 'tr0ngx_canary':
                        _obliterate()
                except Exception:
                    pass
    except Exception:
        pass

    # Vector 17: Core builtin identity watchdog (monkeypatch detection)
    try:
        import builtins as _trx_bi
        _trx_sig = (id(_trx_bi.__import__), id(_trx_bi.open), id(_trx_bi.exec),
                    id(_trx_bi.eval), id(_trx_bi.compile), id(_trx_bi.__build_class__))
        if '_trx_bi_sig' not in globals():
            globals()['_trx_bi_sig'] = _trx_sig
        elif _trx_sig != globals()['_trx_bi_sig']:
            _obliterate()
    except Exception:
        pass

    # Vector 18: Deferred trace escalation (silent one-cycle latch defeats breakpoint-and-inspect)
    try:
        if getattr(sys, 'gettrace', None) and sys.gettrace():
            if globals().get('_trx_trace_latch'):
                _obliterate()
            globals()['_trx_trace_latch'] = True
        else:
            globals()['_trx_trace_latch'] = False
    except Exception:
        pass

    # Vector 19: Linux TracerPid detection (/proc/self/status).
    # Source: pyshield protection/anti_analysis.py TracerPid vector (MIT, research
    # note) - closes the native-gdb-attach gap in the previous matrix.
    try:
        if sys.platform.startswith('linux'):
            with open('/proc/self/status', 'r') as _tps:
                for _tp_line in _tps:
                    if _tp_line.startswith('TracerPid:'):
                        if int(_tp_line.split(':', 1)[1].strip() or '0') != 0:
                            _obliterate()
                        break
    except Exception:
        pass

    # Vector 20: Dual builtins identity cross-check. Fresh import gives a pristine
    # namespace; id() equality catches attribute replacement while the type()
    # equality against print() catches proxy objects spoofing __name__.
    # Source: pyshield anti_analysis.py builtins identity check (MIT, research note).
    try:
        import builtins as _trx_bi2
        import importlib as _trx_il2
        _trx_pristine = _trx_il2.import_module('builtins')
        if id(_trx_bi2.exec) != id(_trx_pristine.exec):
            _obliterate()
        if id(_trx_bi2.compile) != id(_trx_pristine.compile):
            _obliterate()
        if type(_trx_bi2.exec) is not type(_trx_bi2.print):
            _obliterate()
        if type(_trx_bi2.compile) is not type(_trx_bi2.print):
            _obliterate()
        del _trx_pristine
    except SystemExit:
        raise
    except Exception:
        pass

# ═══ ANTI-IMPORT HOOK ═══
class _ImportBlocker:
    '''Block dangerous decompilation & debugger imports at meta_path level (PEP 451 compatible) (TRX-DEOB-009/010)'''
    _BLOCKED = frozenset({
        'uncompyle6', 'decompyle3', 'decompyle++', 'decompyle', 'xdis', 'pycdc', 'bytecode_tools',
        'pydevd', 'debugpy', 'coverage', 'hunter', 'snooper', 'snoop', 'objgraph', 'pympler',
        'unpyc', 'easy_python_decompiler', 'pickletools', 'pydevd_tracing', 'pydevd_bundle'
    })

    def find_spec(self, name, path=None, target=None):
        name_lower = name.lower()
        if any(name_lower == blocked or name_lower.startswith(blocked + '.') for blocked in self._BLOCKED):
            _obliterate()
        return None

    # Legacy fallback for Python < 3.4
    def find_module(self, name, path=None):
        name_lower = name.lower()
        if any(name_lower == blocked or name_lower.startswith(blocked + '.') for blocked in self._BLOCKED):
            return self
        return None

    def load_module(self, name):
        _obliterate()

def _install_import_blocker():
    blocker = _ImportBlocker()
    if blocker not in sys.meta_path:
        sys.meta_path.insert(0, blocker)

# ═══ ANTI-MEMORY DUMP, REFLECTION NEUTRALIZATION & C-LEVEL TRACE PURGE ═══
def _anti_memory_analysis():
    '''Make memory analysis harder, neutralize reflection/bytecode dumpers, wipe linecache, clear tracebacks and wipe C-level trace hooks (TRX-DEOB-009/010)'''
    try:
        gc.collect()
        if hasattr(gc, 'set_debug'):
            gc.set_debug(0)
    except Exception:
        pass

    # Neutralize pure disassembly and debugging tools if already loaded
    for _mod_name, _func_names in [
        ('dis', ['dis', 'show_code', 'disassemble', 'distb', 'disco']),
        ('pdb', ['set_trace', 'Pdb']),
    ]:
        if _mod_name in sys.modules and sys.modules[_mod_name] is not None:
            try:
                _m = sys.modules[_mod_name]
                for _fn in _func_names:
                    if hasattr(_m, _fn):
                        setattr(_m, _fn, lambda *a, **k: None)
            except Exception:
                pass

    # Clear source line cache to prevent debuggers/inspect from extracting original source lines
    try:
        import linecache
        linecache.clearcache()
    except Exception:
        pass

    # Wipe exception/traceback residue from sys
    for attr in ('last_traceback', 'last_value', 'last_type', 'last_exc'):
        if hasattr(sys, attr):
            try:
                delattr(sys, attr)
            except Exception:
                pass

    # Null out Python-level tracing & profiling
    # IMPORTANT: Must use None (not a lambda) so sys.gettrace()/getprofile() return None,
    # otherwise _anti_debugger() will detect a non-None trace and call _obliterate().
    try:
        sys.settrace(None)
        if hasattr(sys, 'setprofile'):
            sys.setprofile(None)
    except Exception:
        pass

# ═══ SELF-INTEGRITY CHECK (BYTECODE OPCODES CHECKSUM) ═══
def _self_verify():
    '''Verify own functions and bytecode opcodes have not been patched or hooked'''
    checks = [_obliterate, _anti_debugger, _verify_builtins,
              _protect_marshal, _anti_memory_analysis]
    for check in checks:
        if not callable(check):
            _obliterate()
        if not isinstance(check, types.FunctionType):
            _obliterate()
        if not hasattr(check, '__code__') or not check.__code__.co_code:
            _obliterate()

# ═══ CONTINUOUS MONITORING THREAD ═══
def _start_watchdog():
    def _monitor():
        _check_count = 0
        while _SHIELD._active:
            try:
                _check_count += 1
                _anti_debugger()
                _verify_builtins()
                _self_verify()
                if '_hidden_check' in dir() and callable(_hidden_check):
                    _hidden_check()

                # Periodic deep scan every 10 checks
                if _check_count % 10 == 0:
                    _anti_memory_analysis()

                # Randomize sleep to avoid timing-based bypass
                time.sleep(random.uniform(0.3, 1.5))
            except SystemExit:
                os._exit(1)
            except Exception:
                pass

    t = threading.Thread(target=_monitor, daemon=True, name=''.join(
        random.choices('abcdefghijklmnop', k=12)))
    t.start()

# ═══ ANTI-MONKEY PATCHING ═══
def _freeze_critical():
    '''Make critical objects harder to monkey-patch'''
    import builtins

    # Store references that can't be easily found
    _hidden = type('', (), {
        '_e': builtins.exec,
        '_v': builtins.eval,
        '_c': builtins.compile,
        '_i': builtins.__import__,
        '_m': marshal.loads,
    })()

    # Verify periodically
    def _check_hidden():
        _safe_names = ('_safe_exec', '_safe_eval', '_guarded_loads', '_safe_loads', '_wrapped', '<lambda>', 'exec', 'eval', 'loads', 'compile')
        _cur_e = getattr(builtins, 'exec', None)
        _cur_v = getattr(builtins, 'eval', None)
        if _cur_e is not None and id(_hidden._e) != id(_cur_e):
            if not (hasattr(_cur_e, '__name__') and _cur_e.__name__ in _safe_names):
                _obliterate()
        if _cur_v is not None and id(_hidden._v) != id(_cur_v):
            if not (hasattr(_cur_v, '__name__') and _cur_v.__name__ in _safe_names):
                _obliterate()
        if id(_hidden._m) != id(marshal.loads.__wrapped__ if hasattr(marshal.loads, '__wrapped__') else marshal.loads):
            pass  # We wrapped it ourselves

    return _check_hidden

# ═══ INITIALIZE ALL PROTECTION ═══
try:
    _snapshot_builtins()
    _anti_debugger()
    _install_import_blocker()
    _protect_marshal()
    _protect_exec_eval()
    _anti_memory_analysis()
    _self_verify()
    _hidden_check = _freeze_critical()
    _start_watchdog()
except SystemExit:
    os._exit(1)
except Exception:
    pass
"""

# ═══════════════════════════════════════════════════════════════
# VELIMATIX ANTI-HOOK ENGINE
# ═══════════════════════════════════════════════════════════════

velimatix_anti_hook = r"""
import traceback as _tb_, marshal as _m_, sys as _s_, types as _tp_, random as _rnd

class _VELIMATIX_SHIELD_(MemoryError): pass

class _VeliGuard_:
    _HOOKED = set()
    _FUNC_TYPES = {}

    @staticmethod
    def _terminate():
        try:
            __import__('gc').collect()
        except: pass
        try:
            __import__('os')._exit(1)
        except Exception:
            raise _VELIMATIX_SHIELD_('>> PROTECTION TRIGGERED <<') from None

    @staticmethod
    def verify_hook(func, module_name):
        # Check if function module looks suspicious (blocklist approach)
        if callable(func) and hasattr(func, '__module__'):
            mod = func.__module__
            if mod and isinstance(mod, str):
                # Blocklist - only block known bad reversing modules
                blocked = ['uncompyle', 'decompyle', 'pycdc', 'xdis', 'pydevd', 'debugpy', 'frida']
                if any(bad in mod.lower() for bad in blocked):
                    _VeliGuard_._HOOKED.add(mod)
                    _VeliGuard_._terminate()

    @staticmethod
    def guard_wrapper(func):
        def _wrapped(*args, **kwargs):
            if args and isinstance(args[0], str) and args[0] in _VeliGuard_._HOOKED:
                _VeliGuard_._terminate()
            return func(*args, **kwargs)
        _wrapped.__module__ = func.__module__
        _wrapped.__name__ = func.__name__
        return _wrapped

    @staticmethod
    def verify_stack():
        try:
            stack = _tb_.extract_stack()
            if stack and isinstance(stack, list):
                for frame in stack[:-2]:
                    fn = frame.filename.lower()
                    if any(bad in fn for bad in ['uncompyle', 'decompyle', 'pycdc', 'xdis', 'pydevd', 'debugpy', 'frida']):
                        _VeliGuard_._terminate()
        except Exception:
            pass

    @staticmethod
    def verify_type_integrity(module_name, func_name):
        mod = __import__(module_name)
        func = getattr(mod, func_name, None)
        if func is None:
            _VeliGuard_._terminate()
        _VeliGuard_._FUNC_TYPES[f"{module_name}.{func_name}"] = type(func)
        _VeliGuard_.verify_hook(func, module_name)

    @staticmethod
    def check_type_changed():
        for key, expected_type in list(_VeliGuard_._FUNC_TYPES.items()):
            parts = key.split('.', 1)
            try:
                mod = __import__(parts[0])
                func = getattr(mod, parts[1], None)
                if func is not None:
                    # Allow builtins/functions wrapped by internal guard closures
                    if type(func) != expected_type and not callable(func):
                        _VeliGuard_._terminate()
            except Exception:
                pass

    @staticmethod
    def protect_marshal():
        import marshal as _real_m
        _real_loads = _real_m.loads
        _real_loads_id = id(_real_loads)

        def _safe_loads(data, *args, **kwargs):
            frame = _s_._getframe(1)
            caller = frame.f_code.co_filename.lower()
            if any(x in caller for x in ['uncompyle', 'decompyle', 'pycdc', 'xdis', 'pydevd', 'debugpy', 'frida']):
                _VeliGuard_._terminate()
            if id(_real_loads) != _real_loads_id:
                _VeliGuard_._terminate()
            return _real_loads(data, *args, **kwargs)

        _real_m.loads = _safe_loads
        _s_.modules['marshal'] = _real_m
        # Update stored type after wrapping to avoid false positives
        _VeliGuard_._FUNC_TYPES['marshal.loads'] = type(_safe_loads)

    @staticmethod
    def anti_monkey_patch():
        import builtins as _b
        _safe_names = ('_safe_exec', '_safe_eval', '_guarded_loads', '_safe_loads', '_wrapped', '<lambda>', 'exec', 'eval', 'loads', 'compile')
        _snapshot = {
            'exec': id(_b.exec),
            'eval': id(_b.eval),
            'compile': id(_b.compile),
            '__import__': id(_b.__import__),
            'open': id(_b.open),
            'getattr': id(_b.getattr),
        }

        def _check_patch():
            for name, orig_id in _snapshot.items():
                current = getattr(_b, name, None)
                if current is None:
                    _VeliGuard_._terminate()
                curr_id = id(current)
                # Allow internal Tr0ngX guard closures and recognized safe wrappers
                _is_known_guard = (
                    hasattr(current, '_func') or
                    curr_id in globals().get('_ORIGINAL_BUILTINS', {}).values() or
                    (hasattr(current, '__name__') and current.__name__ in _safe_names)
                )
                if curr_id != orig_id and not _is_known_guard:
                    _VeliGuard_._terminate()
            _VeliGuard_.check_type_changed()

        return _check_patch

    @staticmethod
    def continuous_guard():
        import threading, time
        # Check if anti-debug shield's watchdog is already running
        # to avoid duplicate patrol threads competing with each other
        _existing_threads = [t.name for t in threading.enumerate()]
        _anti_shield_active = any('_SHIELD' in str(t) for t in threading.enumerate())
        if _anti_shield_active or '_SHIELD' in dir(__builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)):
            # Anti-debug shield already has its own watchdog - skip duplicate
            return

        _checker = _VeliGuard_.anti_monkey_patch()

        def _patrol():
            while True:
                try:
                    _checker()
                    _VeliGuard_.verify_stack()

                    poison = {'pydevd', 'debugpy', 'pdb', 'coverage', 'hunter', 'snooper',
                              'uncompyle6', 'decompyle3', 'xdis', 'bytecode'}
                    if set(_s_.modules.keys()) & poison:
                        _VeliGuard_._terminate()

                    if _s_.gettrace() is not None:
                        _VeliGuard_._terminate()

                    time.sleep(_rnd.uniform(0.5, 2.0))
                except _VELIMATIX_SHIELD_:
                    __import__('os')._exit(1)
                except SystemExit:
                    __import__('os')._exit(1)
                except Exception:
                    pass

        t = threading.Thread(target=_patrol, daemon=True,
                             name=''.join(_rnd.choices('abcdefghijklmnop', k=16)))
        t.start()

    @staticmethod
    def init():
        # protect_marshal MUST come first to update types before we store them
        _VeliGuard_.protect_marshal()
        _VeliGuard_.verify_type_integrity('marshal', 'loads')
        _VeliGuard_.verify_type_integrity('builtins', 'exec')
        _VeliGuard_.verify_type_integrity('builtins', 'eval')
        _VeliGuard_.verify_type_integrity('builtins', 'compile')
        _VeliGuard_.verify_stack()
        _VeliGuard_.continuous_guard()

try:
    _VeliGuard_.init()
except _VELIMATIX_SHIELD_:
    __import__('os')._exit(1)
except SystemExit:
    __import__('os')._exit(1)
except Exception:
    pass
"""


# ======================================================================
# (slice gap filler)
# ======================================================================

# ═══════════════════════════════════════════════════════════════
# SELF-MODIFYING & STEALTH ANTI-TAMPER ENGINE
# ═══════════════════════════════════════════════════════════════

def _generate_self_modify_wrapper():
    """Generate stealth multi-hash anti-tamper and zero-width self-morphing engine."""
    v_fn = rd('state_machine')
    v_sf = rd('guard')
    v_raw = rd('biopaque')
    v_zw = rd('guard')
    v_c = rd('state_machine')
    v_h = rd('state_machine')
    v_sig = rd('guard')
    v_b = rd('state_machine')
    v_fr = rd('guard')
    v_co = rd('state_machine')
    v_bits = rd('state_machine')
    v_nw = rd('guard')

    return f"""
def {v_fn}():
    try:
        import os, sys, hashlib, time
        {v_sf} = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else (__file__ if '__file__' in globals() else None)
        if {v_sf} and os.path.exists({v_sf}):
            with open({v_sf}, 'rb') as {v_raw}:
                _orig_bytes = {v_raw}.read()
            {v_c} = _orig_bytes
            # Multi-layer canonical strip (removes invisible zero-width unicode & trailing spaces)
            {v_zw} = [b'\\xe2\\x80\\x8b', b'\\xe2\\x80\\x8c', b'\\xef\\xbb\\xbf', b'\\xe2\\x80\\x8d']
            for {v_b} in {v_zw}:
                {v_c} = {v_c}.replace({v_b}, b'')
            {v_c} = {v_c}.rstrip()
            {v_h} = hashlib.sha256({v_c}).hexdigest()
            # Frame stack & Merkle Bytecode Verification (co_code + co_consts + co_names)
            try:
                {v_fr} = sys._getframe(1)
                _m_nodes = [{v_fr}.f_code.co_code]
                for _const in {v_fr}.f_code.co_consts:
                    if isinstance(_const, (bytes, str, int, float, bool)):
                        _m_nodes.append(str(_const).encode('utf-8', 'ignore'))
                for _name in {v_fr}.f_code.co_names:
                    _m_nodes.append(_name.encode('utf-8', 'ignore'))
                {v_co} = hashlib.sha256(b''.join(_m_nodes)).hexdigest()
            except Exception:
                {v_co} = {v_h}
            # Anti-hooking integrity: verify builtins/sys trace
            if getattr(sys, 'gettrace', lambda: None)() is not None:
                return
            # Invisible Zero-Width Morphing (Zero plain text markers!)
            {v_bits} = ''.join(f'{{ord({v_b}):08b}}' for {v_b} in {v_h}[:16])
            {v_sig} = '# ' + ''.join('\\u200c' if {v_b} == '1' else '\\u200b' for {v_b} in {v_bits})
            _sig_b = {v_sig}.encode('utf-8')
            if _sig_b not in _orig_bytes:
                {v_nw} = _orig_bytes.rstrip() + b'\\n' + _sig_b
                try:
                    with open({v_sf}, 'wb') as {v_raw}:
                        {v_raw}.write({v_nw})
                except Exception:
                    pass
    except Exception:
        pass

try:
    {v_fn}()
except Exception:
    pass
"""

def _generate_anti_vm_shield() -> str:
    """Generate hyper-strict industrial-grade Anti-VM, Sandbox & Virtual Network detection shield."""
    fn_name = rd('state_machine')
    abort_fn = rd('guard')
    cores_var = rd('biopaque')
    user_var = rd('state_machine')
    host_var = rd('guard')
    
    return f"""
# ═══ ANTI-VIRTUALIZATION, SANDBOX & VIRTUAL NETWORK MATRIX ═══
def {fn_name}():
    import os, sys

    def {abort_fn}():
        try:
            import gc
            gc.collect()
        except Exception:
            pass
        try:
            os._exit(1)
        except Exception:
            sys.exit(1)

    # 1. CPU Core & Memory Quantity Check (Automated analysis sandboxes often allocate <= 1 vCPU or <= 2GB RAM)
    try:
        {cores_var} = os.cpu_count()
        if {cores_var} is not None and {cores_var} <= 1:
            {abort_fn}()
    except Exception:
        pass

    # 2. Known Automated Sandbox Usernames & Hostnames
    try:
        {user_var} = (os.getenv('USERNAME') or os.getenv('USER') or '').upper()
        {host_var} = (os.getenv('COMPUTERNAME') or os.getenv('HOSTNAME') or '').upper()
        _bad_identities = {{'SANDBOX', 'VIRUS', 'MALTEST', 'TEQUILABOOMBOOM', 'SAMPLE', 'CURRENTUSER', 'DESKTOP-ANALYSIS', 'USER-PC', 'JOHN-PC', 'TEST-PC', 'KLONE', 'MALWARE', 'CUCKOO'}}
        if {user_var} in _bad_identities or {host_var} in _bad_identities:
            {abort_fn}()
    except Exception:
        pass

    # 3. Virtual Machine MAC Address OUI & Virtual Network Interface Inspection
    try:
        import uuid
        _mac_num = uuid.getnode()
        _mac_hex = f"{{_mac_num:012x}}".upper()
        _mac_oui = ':'.join([_mac_hex[i:i+2] for i in range(0, 6, 2)])
        # VMware, VirtualBox, Parallels, QEMU/KVM, Xen virtual OUI prefixes
        _bad_ouis = (
            '00:05:69', '00:0C:29', '00:1C:14', '00:50:56', # VMware
            '08:00:27',                                     # VirtualBox
            '00:1C:42',                                     # Parallels
            '52:54:00', '54:52:00',                         # QEMU / KVM
            '00:16:3E',                                     # Xen
            '00:03:FF', '00:15:5D'                          # Microsoft Virtual
        )
        for _bad_prefix in _bad_ouis:
            if _mac_oui.startswith(_bad_prefix):
                {abort_fn}()
    except Exception:
        pass

    # 4. Windows-Specific VM, Virtual Network & Hypervisor Deep Inspection
    if os.name == 'nt':
        # A. Screen Resolution Metrics (Headless sandboxes often have small/default resolution)
        try:
            import ctypes
            if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'user32'):
                _w = ctypes.windll.user32.GetSystemMetrics(0)
                _h = ctypes.windll.user32.GetSystemMetrics(1)
                if 0 < _w < 800 or 0 < _h < 600:
                    {abort_fn}()
        except Exception:
            pass

        # B. System Uptime Check (Fresh sandbox snapshots often have uptime < 60s)
        try:
            import ctypes
            if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'kernel32'):
                _uptime = ctypes.windll.kernel32.GetTickCount64()
                if 0 < _uptime < 60000:
                    {abort_fn}()
        except Exception:
            pass

        # C. VM Artifact & Driver Files Detection
        try:
            _sys_root = os.getenv('SystemRoot', r'C:\\Windows')
            _drv_dir = os.path.join(_sys_root, 'System32', 'drivers')
            _vm_drivers = {{'vboxmouse.sys', 'vboxguest.sys', 'vboxsf.sys', 'vboxvideo.sys',
                           'vmmouse.sys', 'vmhgfs.sys', 'vmusbmouse.sys', 'qemu-ga.exe', 'prl_fs.sys'}}
            if os.path.exists(_drv_dir):
                for _fname in os.listdir(_drv_dir):
                    if _fname.lower() in _vm_drivers:
                        {abort_fn}()
        except Exception:
            pass

        # D. BIOS & Hardware Manufacturer Registry Check
        try:
            import winreg
            _reg_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\\Description\\System\\BIOS"),
                (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\\Description\\System"),
            ]
            _vm_kw = (b'vmware', b'virtualbox', b'innotek', b'qemu', b'bochs', b'kvm', b'parallels', b'xen', b'seabios')
            for _hkey, _subkey in _reg_paths:
                try:
                    with winreg.OpenKey(_hkey, _subkey) as _k:
                        for _i in range(winreg.QueryInfoKey(_k)[1]):
                            _, _vdata, _ = winreg.EnumValue(_k, _i)
                            _vstr = str(_vdata).lower().encode()
                            if any(_kw in _vstr for _kw in _vm_kw):
                                {abort_fn}()
                except Exception:
                    pass
        except Exception:
            pass

        # E. Virtual Disk & SCSI Storage Device Models Check
        try:
            import winreg
            _scsi_reg = r"HARDWARE\\DEVICEMAP\\Scsi"
            _bad_disk_kw = (b'vbox', b'vmware', b'qemu', b'virtio', b'virtual disk', b'parallels')
            def _scan_key_recursive(_hk, _path):
                try:
                    with winreg.OpenKey(_hk, _path) as _k:
                        num_sub, num_val, _ = winreg.QueryInfoKey(_k)
                        for _i in range(num_val):
                            _vn, _vd, _ = winreg.EnumValue(_k, _i)
                            _vd_bytes = str(_vd).lower().encode()
                            if any(_kw in _vd_bytes for _kw in _bad_disk_kw):
                                {abort_fn}()
                        for _j in range(num_sub):
                            _sub_name = winreg.EnumKey(_k, _j)
                            _scan_key_recursive(_hk, _path + chr(92) + _sub_name)
                except Exception:
                    pass
            _scan_key_recursive(winreg.HKEY_LOCAL_MACHINE, _scsi_reg)
        except Exception:
            pass

        # F. Virtual Network Adapters Registry & Sandboxed NAT Gateway Inspection
        try:
            import winreg
            _net_class_reg = r"SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e972-e325-11ce-bfc1-08002be10318}}"
            _vm_net_kw = (b'virtualbox', b'vmware accelerated', b'vmware virtual', b'red hat virtio', b'parallels virtual', b'qemu virtio')
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _net_class_reg) as _net_key:
                for _idx in range(winreg.QueryInfoKey(_net_key)[0]):
                    try:
                        _sk_name = winreg.EnumKey(_net_key, _idx)
                        if _sk_name.isdigit():
                            with winreg.OpenKey(_net_key, _sk_name) as _dev_key:
                                try:
                                    _desc, _ = winreg.QueryValueEx(_dev_key, "DriverDesc")
                                    _desc_b = str(_desc).lower().encode()
                                    if any(_kw in _desc_b for _kw in _vm_net_kw):
                                        {abort_fn}()
                                except Exception:
                                    pass
                    except Exception:
                        pass
        except Exception:
            pass

    # 5. Linux & POSIX Container / VM Deep Inspection
    if os.name == 'posix':
        try:
            _dmi_files = ['/sys/class/dmi/id/product_name', '/sys/class/dmi/id/sys_vendor', '/sys/class/dmi/id/board_vendor', '/sys/hypervisor/type']
            _vm_tags = ['virtualbox', 'vmware', 'qemu', 'kvm', 'bochs', 'xen', 'innotek', 'parallels', 'hyper-v']
            for _dpath in _dmi_files:
                if os.path.exists(_dpath):
                    with open(_dpath, 'r', errors='ignore') as _df:
                        _dcontent = _df.read().lower()
                        if any(_t in _dcontent for _t in _vm_tags):
                            {abort_fn}()
        except Exception:
            pass

        # Network interface MAC & driver on Linux
        try:
            if os.path.exists('/sys/class/net'):
                for _iface in os.listdir('/sys/class/net'):
                    _addr_file = os.path.join('/sys/class/net', _iface, 'address')
                    if os.path.isfile(_addr_file):
                        with open(_addr_file, 'r', errors='ignore') as _af:
                            _mac_line = _af.read().strip().upper()
                            for _bp in ('00:05:69', '00:0C:29', '00:50:56', '08:00:27', '52:54:00', '00:1C:42'):
                                if _mac_line.startswith(_bp):
                                    {abort_fn}()
        except Exception:
            pass

        try:
            if os.path.exists('/.dockerenv') or os.path.exists('/run/systemd/container'):
                {abort_fn}()
        except Exception:
            pass

try:
    {fn_name}()
except Exception:
    pass
"""


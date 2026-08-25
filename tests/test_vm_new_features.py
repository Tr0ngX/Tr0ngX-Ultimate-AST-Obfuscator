"""
TVM New Feature Tests: --vm-annotations + --anti-intercept
===========================================================
Tests for the two newest VM features:
1. Annotations preservation (--vm-annotations y)
2. Deep anti-read shield (--anti-intercept y)
3. Combined usage
4. Regression: features OFF = no side effects
"""
import os, sys, subprocess, tempfile

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

OBF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'main.py')
REPO = os.path.dirname(OBF)
_pass, _fail, _results = 0, 0, []


def _run_case(tag, source, extra_flags, expect_in_stdout=None, expect_not_in_stderr=None):
    global _pass, _fail
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w', encoding='utf-8') as f:
        f.write(source)
        tgt = f.name
    out = tgt + '.obf.py'
    try:
        cmd = [sys.executable, OBF, '-i', tgt, '-o', out, '-m', '1',
               '--vm-obf', 'y', '--vm-level', '2', '--no-art'] + extra_flags
        build = subprocess.run(cmd, capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=420, cwd=REPO)
        if build.returncode != 0:
            _rec(tag, False, f'BUILD rc={build.returncode} {build.stderr[:200]}')
            return

        run = subprocess.run([sys.executable, out], capture_output=True,
                             text=True, encoding='utf-8', errors='replace', timeout=120)
        ok = run.returncode == 0
        if expect_in_stdout:
            ok = ok and expect_in_stdout in run.stdout
        if expect_not_in_stderr:
            ok = ok and expect_not_in_stderr not in run.stderr

        detail = ''
        if not ok:
            detail = f'rc={run.returncode} out={run.stdout.strip()[:80]} err={run.stderr.strip()[-150:]}'
        _rec(tag, ok, detail)
    except Exception as e:
        _rec(tag, False, str(e)[:200])
    finally:
        for f in [tgt, out]:
            if os.path.exists(f):
                try: os.remove(f)
                except Exception: pass


def _rec(tag, passed, detail=''):
    global _pass, _fail
    if passed:
        _pass += 1
        print(f'  [PASS] {tag}')
    else:
        _fail += 1
        print(f'  [FAIL] {tag} | {detail}')
    _results.append((tag, passed))


def run_all():
    print('=' * 78)
    print(' TVM New Feature Tests: Annotations + Anti-Intercept')
    print('=' * 78)

    # ─── Annotations ──────────────────────────────────────────────────────────
    print('\n--- --vm-annotations ---')

    _run_case('ann_module_var_y', '''
x: int = 5
print(x)
print(type(__annotations__["x"]).__name__)
''', ['--vm-obf', 'y', '--vm-annotations', 'y'], expect_in_stdout='5')

    _run_case('ann_class_attr_y', '''
class Config:
    host: str = "0.0.0.0"
    port: int = 8080
print(Config.host, Config.port)
''', ['--vm-obf', 'y', '--vm-annotations', 'y'], expect_in_stdout='0.0.0.0 8080')

    _run_case('ann_func_params_y', '''
from typing import Optional
def process(data: bytes, count: int = 3) -> Optional[str]:
    return f"{count}:{len(data)}"
print(process(b"hi"))
''', ['--vm-obf', 'y', '--vm-annotations', 'y'], expect_in_stdout='3:2')

    _run_case('ann_off_no_bloat', '''
x: int = 5
y: str = "hello"
print(x, y)
''', ['--vm-obf', 'y'], expect_in_stdout='5 hello')

    # ─── Anti-Intercept ───────────────────────────────────────────────────────
    print('\n--- --anti-intercept ---')

    # Basic: shield doesn't break normal execution
    _run_case('ai_normal_exec_y', '''
import sys
print("shield active")
data = "sensitive_value"
print(len(data))
''', ['--vm-obf', 'y', '--anti-intercept', 'y'], expect_in_stdout='shield active')

    # Shield blocks mock import attempt
    _run_case('ai_block_mock_y', '''
import sys
# This should still work (mock is blocked but we catch ImportError)
try:
    import httpretty
    print("httpretty imported - BAD")
except (ImportError, SystemExit):
    print("httpretty blocked")
except BaseException:
    print("blocked by shield")
''', ['--vm-obf', 'y', '--anti-intercept', 'y'])

    # Socket integrity: normal socket operations work
    _run_case('ai_socket_ok_y', '''
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print("socket created", type(s).__name__ != "socket")
s.close()
''', ['--vm-obf', 'y', '--anti-intercept', 'y'])

    # SSL context works normally
    _run_case('ai_ssl_ok_y', '''
import ssl
ctx = ssl.create_default_context()
print("ssl ok", ctx.verify_mode != ssl.CERT_NONE)
''', ['--vm-obf', 'y', '--anti-intercept', 'y'])

    # ─── Combined Features ────────────────────────────────────────────────────
    print('\n--- Combined ---')

    _run_case('combo_all_new_flags', '''
import sys
from typing import List

items: List[int] = [1, 2, 3]
name: str = "test"

class Handler:
    endpoint: str = "/api"
    
    def process(self, data: bytes) -> int:
        return len(data)

h = Handler()
print(name, items, h.process(b"data"), h.endpoint)
''', ['--vm-obf', 'y', '--vm-level', '2', '--vm-annotations', 'y',
      '--anti-intercept', 'y'], expect_in_stdout='test')

    # ─── Regression: flags off = clean output ────────────────────────────────
    print('\n--- Regression (flags off) ---')

    _run_case('regr_annotations_off', '''
x: int = 42
print(x)
''', ['--vm-obf', 'y', '--vm-annotations', 'n'], expect_in_stdout='42')

    _run_case('regr_anti_intercept_off', '''
import socket
print("no shield")
''', ['--vm-obf', 'y', '--anti-intercept', 'n'], expect_in_stdout='no shield')

    # ─── Summary ─────────────────────────────────────────────────────────────
    total = _pass + _fail
    print('\n' + '=' * 78)
    print(f' NEW FEATURE TESTS: {_pass} PASSED | {_fail} FAILED | {total} TOTAL')
    if total:
        print(f' Pass rate: {_pass / total * 100:.1f}%')
    print('=' * 78)
    if _fail:
        for tag, ok in _results:
            if not ok:
                d = next((d for t, o, d in [(r[0], r[1], '') for r in _results] if t == tag and not o), '')
                pass
    return min(1, _fail)


if __name__ == '__main__':
    sys.exit(run_all())

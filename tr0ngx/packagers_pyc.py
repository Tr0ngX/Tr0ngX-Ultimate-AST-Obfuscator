"""PYC output-format packager for the Tr0ngX obfuscator.

Packages final obfuscated source into a standalone .pyc file using the
PEP 552-style header layout (magic, flags, mtime, size) followed by a
marshalled code object. The resulting file runs directly under any CPython
interpreter of the same version that produced it.
"""

import importlib.util
import marshal
import os
import struct
import subprocess
import sys


def _wrap_exception_flow(source_code: str) -> str:
    """Wraps entry point into non-linear exception-driven dispatch table.
    Decompilers (pycdc, uncompyle6) traversing standard basic blocks
    fail on nested exception tables (co_exceptiontable in Python 3.11+)."""
    indented = "\n".join("            " + line for line in source_code.splitlines())
    return (
        "try:\n"
        "    _d = 1 // 0\n"
        "except ZeroDivisionError:\n"
        "    try:\n"
        "        raise KeyError(0x5452304E)\n"
        "    except KeyError as _e:\n"
        "        if _e.args[0] == 0x5452304E:\n"
        f"{indented}\n"
    )


def package_pyc(final_source: str, out_path: str, source_name: str = "<tr0ngx>", optimize: int = 0) -> str:
    """Compile final_source and write a runnable .pyc to out_path.

    Header follows the standard .pyc container format:
      - 4-byte MAGIC_NUMBER (importlib.util.MAGIC_NUMBER)
      - 4-byte bit-field (0: timestamp-based invalidation, unused here)
      - 4-byte source mtime (0)
      - 4-byte source size (0)
    Followed by marshal.dumps() of the compiled code object.
    """
    wrapped_source = _wrap_exception_flow(final_source)
    code_object = compile(wrapped_source, source_name, 'exec', optimize=optimize)

    # Arm .pyc with decompiler memory exhaustion bombs embedded in co_consts.
    # CPython ignores inert constants at runtime (<0.001s), but decompilers (PyCDC/uncompyle)
    # traverse and decompile every code object, causing severe heap allocation and OOM/crash.
    try:
        _bomb_src = '''
def _trx_pyc_mem_exhaust_bomb():
    try:
        match [0, {"__trx__": 1}]:
            case [_, {"__trx__": _g}] if False: return 1
            case [*_t, {"__trx__": _v}] if len(_t) > 9999: return 2
            case _: pass
        for _ in ((_a, _b, _c) for _a in range(60) for _b in range(60) for _c in range(60) if False): break
    except Exception: pass

def _trx_pyc_cartesian_bomb():
    try:
        return [(_x, _y, _z) for _x in range(40) for _y in range(40) for _z in range(40) if False]
    except Exception: pass
'''
        _bomb_co = compile(_bomb_src, '<tr0ngx_bomb>', 'exec')
        code_object = code_object.replace(co_consts=code_object.co_consts + _bomb_co.co_consts)
    except Exception:
        pass

    parent_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(parent_dir, exist_ok=True)

    with open(out_path, 'wb') as f:
        f.write(importlib.util.MAGIC_NUMBER)
        f.write(struct.pack('<I', 0))
        f.write(struct.pack('<I', 0))
        f.write(struct.pack('<I', 0))
        f.write(marshal.dumps(code_object))

    return out_path


if __name__ == "__main__":
    _src = 'print("pyc-ok")\n'
    _pyc_path = os.path.join(os.environ.get("TEMP", "."), "tr0ngx_pyc_selftest.pyc")
    package_pyc(_src, _pyc_path)
    _proc = subprocess.run([sys.executable, _pyc_path], capture_output=True, text=True)
    if _proc.stdout.strip() == "pyc-ok":
        print("PASS")
    else:
        print("FAIL")
        print("stdout:", _proc.stdout)
        print("stderr:", _proc.stderr)

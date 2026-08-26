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


def package_pyc(final_source: str, out_path: str, source_name: str = "<tr0ngx>", optimize: int = 0) -> str:
    """Compile final_source and write a runnable .pyc to out_path.

    Header follows the standard .pyc container format:
      - 4-byte MAGIC_NUMBER (importlib.util.MAGIC_NUMBER)
      - 4-byte bit-field (0: timestamp-based invalidation, unused here)
      - 4-byte source mtime (0)
      - 4-byte source size (0)
    Followed by marshal.dumps() of the compiled code object.
    """
    code_object = compile(final_source, source_name, 'exec', optimize=optimize)

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

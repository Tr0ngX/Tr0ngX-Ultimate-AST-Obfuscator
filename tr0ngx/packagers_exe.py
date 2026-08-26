# -*- coding: utf-8 -*-
"""Standalone .exe output-format packager (Windows-first) for Tr0ngX.

Wraps a final obfuscated source payload into a single self-contained
Windows executable via PyInstaller's programmatic API
(``PyInstaller.__main__.run``). No shell invocation, no auto-install:
if PyInstaller is missing the caller gets an explicit RuntimeError with
the exact fix command.
"""

import os
import subprocess
import sys

__all__ = ["package_exe"]


def package_exe(source_code: str, work_dir: str, out_path: str, app_name: str = None) -> str:
    """Package ``source_code`` into a standalone console .exe.

    Args:
        source_code: Final Python source text to embed as the entry script.
        work_dir: Scratch/build directory (entry script, spec file and the
            PyInstaller ``_build`` workspace are created inside it).
        out_path: Desired output executable path. Its parent directory is
            used as ``--distpath``; its stem is the default ``app_name``.
        app_name: Optional explicit application name; defaults to the stem
            of ``out_path``.

    Returns:
        The absolute path of the produced executable.

    Raises:
        NotImplementedError: On non-Windows platforms.
        RuntimeError: If PyInstaller is not installed, or if the build did
            not produce the expected executable.
    """
    # Windows-first guard: exe packaging targets Windows loaders only.
    if sys.platform != "win32":
        raise NotImplementedError("exe packaging is Windows-first")

    # Locate PyInstaller without auto-installing anything.
    try:
        import PyInstaller  # noqa: F401
        import PyInstaller.__main__ as pyi_main
    except ImportError:
        raise RuntimeError(
            "PyInstaller is required for standalone .exe packaging but is "
            "not installed. Fix with:  pip install pyinstaller"
        )

    work_dir = os.path.abspath(work_dir)
    os.makedirs(work_dir, exist_ok=True)

    out_path = os.path.abspath(out_path)
    dist_dir = os.path.dirname(out_path) or "."
    os.makedirs(dist_dir, exist_ok=True)

    if app_name is None or not app_name:
        app_name = os.path.splitext(os.path.basename(out_path))[0]

    # Write the final payload as the temporary entry script.
    entry_path = os.path.join(work_dir, "_trx_entry.py")
    with open(entry_path, "w", encoding="utf-8") as fh:
        fh.write(source_code)

    build_workpath = os.path.join(work_dir, "_build")

    args = [
        "--onefile",
        "--console",
        "--distpath", dist_dir,
        "--workpath", build_workpath,
        "--specpath", work_dir,
        "--name", app_name,
        entry_path,
    ]

    pyi_main.run(args)

    produced = os.path.join(dist_dir, app_name + ".exe")
    if not os.path.isfile(produced):
        raise RuntimeError(
            "PyInstaller reported success but no executable was produced at: %s" % produced
        )
    return produced


def _self_test() -> int:
    """Self-test: package print("exe-ok") and run the produced exe."""
    import tempfile

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("SKIPPED_NO_PYINSTALLER - install with: pip install pyinstaller")
        return 0

    tmp_root = tempfile.mkdtemp(prefix="trx_exe_selftest_")
    work_dir = os.path.join(tmp_root, "work")
    out_path = os.path.join(tmp_root, "dist", "trx_selftest.exe")

    ok = False
    err_msg = None
    try:
        exe = package_exe('print("exe-ok")\n', work_dir, out_path)
        proc = subprocess.run(
            [exe], capture_output=True, text=True, timeout=120
        )
        stdout = (proc.stdout or "").strip()
        if "exe-ok" in stdout:
            print("PASS - exe ran and printed: %r" % stdout)
            ok = True
        else:
            err_msg = "unexpected exe output: rc=%d stdout=%r stderr=%r" % (
                proc.returncode, stdout, (proc.stderr or "")[:500]
            )
    except Exception as exc:  # noqa: BLE001
        err_msg = "%s: %s" % (type(exc).__name__, exc)

    # Best-effort cleanup of the scratch tree.
    try:
        import shutil
        shutil.rmtree(tmp_root, ignore_errors=True)
    except Exception:
        pass

    if ok:
        return 0
    print("FAIL - %s" % err_msg)
    return 1


if __name__ == "__main__":
    sys.exit(_self_test())

import os, sys, re

def fix_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = content.replace('_v(" \n ══════════════════════ PERFORMANCE & BOTTLENECK PROFILE ══════════════════════")', '_v("")\n    _v(" ══════════════════════ PERFORMANCE & BOTTLENECK PROFILE ══════════════════════")')
    content = content.replace('_v(" \r\n ══════════════════════ PERFORMANCE & BOTTLENECK PROFILE ══════════════════════")', '_v("")\n    _v(" ══════════════════════ PERFORMANCE & BOTTLENECK PROFILE ══════════════════════")')
    content = content.replace(' ═════════════════════════════════════════════════════════════════════════════\n")', ' ═════════════════════════════════════════════════════════════════════════════")\n    _v("")')

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

fix_file(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
fix_file(r"C:\Users\trong\Downloads\procheck.py")
print("Fixed string newlines cleanly!")

import os, sys

def fix_except(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    bad_block = """try:
    import pystyle
    _HAS_PYSTYLE = True
except ImportError:
    
_HAS_PYSTYLE = False"""

    good_block = """try:
    import pystyle
    _HAS_PYSTYLE = True
except ImportError:
    _HAS_PYSTYLE = False"""

    content = content.replace(bad_block, good_block)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

fix_except(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
fix_except(r"C:\Users\trong\Downloads\procheck.py")
print("Fixed except block indentation cleanly!")

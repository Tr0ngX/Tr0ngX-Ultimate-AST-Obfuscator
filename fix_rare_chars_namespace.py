import os, sys, re

def fix_rare_chars_class(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace _RARE_CHARS_POOL definition
    old_pool_def = """_RARE_CHARS_POOL = None  # Lazy-init to save startup time

def _init_rare_chars():
    global _RARE_CHARS_POOL
    if _RARE_CHARS_POOL is not None:
        return
    pool = []"""

    new_pool_def = """class _RareChars:
    pool = None

def _init_rare_chars():
    if _RareChars.pool is not None:
        return
    pool = []"""

    content = content.replace(old_pool_def, new_pool_def)
    content = content.replace("_RARE_CHARS_POOL = [c for c in pool if c.isidentifier()]", "_RareChars.pool = [c for c in pool if c.isidentifier()]")
    content = content.replace("random.choices(_RARE_CHARS_POOL,", "random.choices(_RareChars.pool,")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

fix_rare_chars_class(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
fix_rare_chars_class(r"C:\Users\trong\Downloads\procheck.py")
print("Replaced _RARE_CHARS_POOL with _RareChars.pool namespace cleanly!")

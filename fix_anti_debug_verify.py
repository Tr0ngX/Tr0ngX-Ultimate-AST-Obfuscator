import os, sys

def fix_anti_debug_self_trigger(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Make _verify_builtins resilient and avoid self-triggering
    old_verify = """def _verify_builtins():
    '''Detect if any builtin was hooked/replaced'''
    import builtins
    for name, orig_id in _ORIGINAL_BUILTINS.items():
        current = getattr(builtins, name, None)
        if current is None or id(current) != orig_id:
            _obliterate()"""

    new_verify = """def _verify_builtins():
    '''Detect if any builtin was hooked/replaced'''
    import builtins
    for name, orig_id in _ORIGINAL_BUILTINS.items():
        current = getattr(builtins, name, None)
        if current is None:
            _obliterate()
        curr_id = id(current)
        if curr_id != orig_id and not hasattr(current, '_func'):
            _obliterate()"""

    content = content.replace(old_verify, new_verify)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

fix_anti_debug_self_trigger(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
fix_anti_debug_self_trigger(r"C:\Users\trong\Downloads\procheck.py")
print("Fixed anti-debug builtin verification false positive!")

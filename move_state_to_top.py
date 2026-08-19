import os, sys

def move_engine_state_to_top(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract class _EngineState
    state_class_pattern = """class _EngineState:
    verbose_debug = False
    profile_mode = False
    strict_mode = False
    log_file_path = None
    cli_quiet_mode = False
    use_cjk_names = False
    use_homoglyph_names = False
    use_rare_unicode_names = False
    use_fused_names = False
"""

    content = content.replace(state_class_pattern, "")
    
    # Place right after imports
    target_pos = "_HAS_PYSTYLE = False"
    content = content.replace(target_pos, state_class_pattern + "\n" + target_pos)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

move_engine_state_to_top(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
move_engine_state_to_top(r"C:\Users\trong\Downloads\procheck.py")
print("Moved _EngineState to top of file cleanly!")

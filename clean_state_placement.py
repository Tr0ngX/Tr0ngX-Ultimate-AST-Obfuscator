import os, sys

def clean_state_class(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Clean up duplicated _EngineState blocks
    import re
    content = re.sub(r'class _EngineState:[\s\S]*?use_fused_names = False\n', '', content)
    content = content.replace("_HAS_PYSTYLE = False\n_HAS_PSUTIL = False\n\n_HAS_PYSTYLE = False", "_HAS_PYSTYLE = False\n_HAS_PSUTIL = False")

    state_class_def = """
class _EngineState:
    verbose_debug = False
    profile_mode = False
    strict_mode = False
    log_file_path = None
    cli_quiet_mode = False
    use_cjk_names = False
    use_homoglyph_names = False
    use_rare_unicode_names = False
    use_fused_names = False

_HAS_PYSTYLE = False
_HAS_PSUTIL = False
"""

    content = content.replace("_HAS_PYSTYLE = False\n_HAS_PSUTIL = False", state_class_def.strip())

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

clean_state_class(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
clean_state_class(r"C:\Users\trong\Downloads\procheck.py")
print("Cleaned up _EngineState placement!")

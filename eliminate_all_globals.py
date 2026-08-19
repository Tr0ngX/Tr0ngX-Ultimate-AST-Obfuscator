import os, sys, re

def eliminate_globals(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. State class definition
    state_class_def = """class _EngineState:
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

    if "class _EngineState:" not in content:
        content = content.replace("class _RareChars:", state_class_def + "\nclass _RareChars:")

    # 2. Replace boolean flags with _EngineState attributes
    content = content.replace("_VERBOSE_DEBUG", "_EngineState.verbose_debug")
    content = content.replace("_PROFILE_MODE", "_EngineState.profile_mode")
    content = content.replace("_STRICT_MODE", "_EngineState.strict_mode")
    content = content.replace("_LOG_FILE_PATH", "_EngineState.log_file_path")
    content = content.replace("_CLI_QUIET_MODE", "_EngineState.cli_quiet_mode")
    content = content.replace("_USE_CJK_NAMES", "_EngineState.use_cjk_names")
    content = content.replace("_USE_HOMOGLYPH_NAMES", "_EngineState.use_homoglyph_names")
    content = content.replace("_USE_RARE_UNICODE_NAMES", "_EngineState.use_rare_unicode_names")
    content = content.replace("_USE_FUSED_NAMES", "_EngineState.use_fused_names")

    # 3. Remove all remaining 'global ...' lines
    content = re.sub(r'^\s*global\s+.*$', '', content, flags=re.MULTILINE)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

eliminate_globals(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
eliminate_globals(r"C:\Users\trong\Downloads\procheck.py")
print("100% of all global statements eliminated cleanly!")

import os, sys, re

def clean_globals(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. obfstr
    content = content.replace("def obfstr(v):\n    global _join, _hexrun, _list, _map", "def obfstr(v):")
    content = content.replace("def obfstr(v):\r\n    global _join, _hexrun, _list, _map", "def obfstr(v):")

    # 2. rd()
    content = content.replace("def rd(scope='general'):\n    global _USE_CJK_NAMES, _USE_HOMOGLYPH_NAMES, _USE_RARE_UNICODE_NAMES, _USE_FUSED_NAMES", "def rd(scope='general'):")
    content = content.replace("def rd(scope='general'):\r\n    global _USE_CJK_NAMES, _USE_HOMOGLYPH_NAMES, _USE_RARE_UNICODE_NAMES, _USE_FUSED_NAMES", "def rd(scope='general'):")

    # 3. randomize_name()
    content = content.replace("    def randomize_name(alphabet: str, length: int) -> str:\n        global _USE_CJK_NAMES", "    def randomize_name(alphabet: str, length: int) -> str:")
    content = content.replace("    def randomize_name(alphabet: str, length: int) -> str:\r\n        global _USE_CJK_NAMES", "    def randomize_name(alphabet: str, length: int) -> str:")

    # 4. _show_banner()
    content = content.replace("def _show_banner():\n    if _CLI_QUIET_MODE:\n        return\n    global banner", "def _show_banner():\n    if _CLI_QUIET_MODE:\n        return")
    content = content.replace("def _show_banner():\r\n    if _CLI_QUIET_MODE:\r\n        return\r\n    global banner", "def _show_banner():\r\n    if _CLI_QUIET_MODE:\r\n        return")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

clean_globals(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
clean_globals(r"C:\Users\trong\Downloads\procheck.py")
print("Cleaned all unnecessary global declarations!")

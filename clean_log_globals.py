import os, sys

def clean_log_globals(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = content.replace("def _log_debug(msg: str, stage: str = None, duration: float = None, error: Exception = None, level: str = \"INFO\"):\n    global _LOG_ENTRIES", "def _log_debug(msg: str, stage: str = None, duration: float = None, error: Exception = None, level: str = \"INFO\"):")
    content = content.replace("def _log_debug(msg: str, stage: str = None, duration: float = None, error: Exception = None, level: str = \"INFO\"):\r\n    global _LOG_ENTRIES", "def _log_debug(msg: str, stage: str = None, duration: float = None, error: Exception = None, level: str = \"INFO\"):")

    content = content.replace("def _log_stage_error(stage_name: str, exc: Exception):\n    global _STAGE_ERRORS", "def _log_stage_error(stage_name: str, exc: Exception):")
    content = content.replace("def _log_stage_error(stage_name: str, exc: Exception):\r\n    global _STAGE_ERRORS", "def _log_stage_error(stage_name: str, exc: Exception):")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

clean_log_globals(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
clean_log_globals(r"C:\Users\trong\Downloads\procheck.py")
print("Removed global _LOG_ENTRIES and global _STAGE_ERRORS successfully!")

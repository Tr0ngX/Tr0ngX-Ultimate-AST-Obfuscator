import os, sys

def insert_profile_call(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    target = '_v(" OBFUSCATION COMPLETE!")'
    replacement = """if _PROFILE_MODE or _VERBOSE_DEBUG:
            _print_profile_waterfall(elapsed, original_size, file_size)
        _export_log_file()
        _v(" OBFUSCATION COMPLETE!")"""

    if "_print_profile_waterfall(elapsed" not in content:
        content = content.replace(target, replacement)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Inserted profile waterfall into {file_path}")
    else:
        print(f"Profile waterfall already present in {file_path}")

insert_profile_call(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
insert_profile_call(r"C:\Users\trong\Downloads\procheck.py")

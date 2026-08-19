import os, sys

def fix_velimatix_repr(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = content.replace("_fn_t(VE(LI(MATIX({b}))), globals())()", "_fn_t(VE(LI(MATIX({b!r}))), globals())()")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

fix_velimatix_repr(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
fix_velimatix_repr(r"C:\Users\trong\Downloads\procheck.py")
print("Fixed _velimatix_compile b!r formatting cleanly!")

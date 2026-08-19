import os, sys

def fix_anti_pycdc(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    bad_anti = """ANTI_PYCDC = f\"\"\"
def 你器(你):
    return 你
try:pass
except:pass
finally:pass
{antipycdc}
finally:int(2008-2006)
\"\"\""""

    good_anti = """ANTI_PYCDC = f\"\"\"
def 你器(你):
    return 你
try:
    pass
except:
    pass
finally:
    pass
{antipycdc}
\"\"\""""

    content = content.replace(bad_anti, good_anti)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

fix_anti_pycdc(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
fix_anti_pycdc(r"C:\Users\trong\Downloads\procheck.py")
print("Fixed ANTI_PYCDC block cleanly!")

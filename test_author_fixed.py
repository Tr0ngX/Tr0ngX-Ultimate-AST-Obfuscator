import sys
target_ver_str = '3.14'
checkver = f'''import sys
if not sys.version.startswith('{target_ver_str}'):
    print("Python version mismatch! This script requires Python {target_ver_str}. Current: " + sys.version.split()[0])
    __import__("os")._exit(1)
'''

author = f'''((
    ((([["TRONGDEPZAI-DEV x VELIMATIX x PYCOOL MAXIMUM POWER"],
    ["https://github.com/hngocuyen/trongdepzai-dev/"],
    ["PYTHON AST OBFUSCATOR v4.0 - PYCOOL CJK EDITION"],
    3.11
    ],
    [__import__("builtins").exec(
    {checkver.encode()})
    ])
    )
    )
    )
)
'''
try:
    compile(author, '<test>', 'exec')
    print('Author block compiled successfully!')
except Exception as e:
    print('Author compile error:', e)

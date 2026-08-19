s = '''
    ((
        ((([["TRONGDEPZAI-DEV x VELIMATIX x PYCOOL MAXIMUM POWER"],
        ["https://github.com/hngocuyen/trongdepzai-dev/"],
        ["PYTHON AST OBFUSCATOR v4.0 - PYCOOL CJK EDITION"],
        3.11
        ],
        [__import__("builtins").exec(
        b'print(1)')
        ])
                    )
                )
            )
        )
'''
try:
    compile(s, '<test>', 'exec')
    print('Valid compile!')
except Exception as e:
    print('Compile failed:', type(e), e)

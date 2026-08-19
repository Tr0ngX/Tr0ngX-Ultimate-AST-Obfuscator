import traceback
try:
    with open('obf_final_fixed.py', 'r', encoding='utf-8') as f:
        code = f.read()
    exec(code, {'__name__': '__main__', '__file__': 'obf_final_fixed.py'})
except Exception as e:
    traceback.print_exc()

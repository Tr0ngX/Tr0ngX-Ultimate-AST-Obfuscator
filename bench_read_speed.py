import time
t0 = time.time()
with open('obf_final.py', 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()
t1 = time.time()
print(f'Read in {t1-t0:.2f}s! Text len: {len(text)}')
has_print = 'print' in text
has_input = 'input' in text
print(f'Checked keywords in {time.time()-t1:.2f}s! has_print: {has_print}, has_input: {has_input}')

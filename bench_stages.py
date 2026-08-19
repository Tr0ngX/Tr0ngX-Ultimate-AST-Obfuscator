import sys
sys.path.insert(0, r'C:\Users\trong\Downloads')
import procheck
import time

with open('complex_benchmark.py', 'r', encoding='utf-8-sig') as f:
    orig = f.read().lstrip('\ufeff')

t0 = time.time()
c = procheck._syntax(orig)
print(f'1. _syntax: {time.time() - t0:.2f}s, len: {len(c)}')

t0 = time.time()
c = procheck.__moreobf(c)
print(f'2. __moreobf: {time.time() - t0:.2f}s, len: {len(c)}')

t0 = time.time()
c = procheck.anti + c
c = procheck.velimatix_anti_hook + c
c = procheck._generate_self_modify_wrapper() + c
print(f'3. anti/selfmod: {time.time() - t0:.2f}s, len: {len(c)}')

t0 = time.time()
c = procheck._velimatix_obf(c, mode=3)
print(f'4. _velimatix_obf: {time.time() - t0:.2f}s, len: {len(c)}')

t0 = time.time()
c = procheck.obf(c)
print(f'5. obf(c): {time.time() - t0:.2f}s, len: {len(c)}')

import sys
sys.path.insert(0, r'C:\Users\trong\Downloads')
import procheck
import time

with open('complex_benchmark.py', 'r', encoding='utf-8-sig') as f:
    orig = f.read().lstrip('\ufeff')

c = procheck._syntax(orig)
c = procheck.__moreobf(c)
c = procheck.anti + c
c = procheck.velimatix_anti_hook + c
c = procheck._generate_self_modify_wrapper() + c

t0 = time.time()
c = procheck._velimatix_obf(c, mode=3)
print(f'4. _velimatix_obf mode 3 done in {time.time()-t0:.2f}s, len: {len(c)}')

t0 = time.time()
c = procheck.obf(c)
print(f'5. obf(c) done in {time.time()-t0:.2f}s, len: {len(c)}')

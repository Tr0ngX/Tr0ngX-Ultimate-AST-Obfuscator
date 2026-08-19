import time
alpha = 'abcdefghijklmnopqrstuvwxyz0123456789'
lookup = {c: alpha[alpha.index(c)+1] if alpha.index(c)+1 < len(alpha) else alpha[0] for c in alpha}

# Method 1: .index() inside comprehension
s = 'abc012xyz89' * 100000
t0 = time.time()
r1 = ''.join(c if c not in alpha else alpha[alpha.index(c)+1 if alpha.index(c)+1<len(alpha) else 0] for c in s)
t1 = time.time() - t0

# Method 2: str.translate
table = str.maketrans({c: alpha[(alpha.index(c)+1)%len(alpha)] for c in alpha})
t0 = time.time()
r2 = s.translate(table)
t2 = time.time() - t0

print(f'Comprehension with .index(): {t1:.4f}s')
print(f'str.translate: {t2:.4f}s ({t1/t2:.1f}x faster)')
print('Results identical:', r1 == r2)

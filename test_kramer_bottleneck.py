import time
alpha = 'abcdefghijklmnopqrstuvwxyz0123456789'
key = 12345

# Mocking 6MB of payload after Kyrie Caesar shift
s_raw = ('x = ' + 'a' * 30 + '\n') * 200000 # ~6.8 MB
print('Length of test string:', len(s_raw))

# Test lambda 4 logic timing:
t0 = time.time()
part1 = ''.join(chr(ord(t)-key) if t!='ζ' else '\n' for t in s_raw)
print(f'Part 1 (chr/ord loop): {time.time()-t0:.2f}s')

t0 = time.time()
part2 = ''.join(c if c not in alpha else alpha[alpha.index(c)+1 if alpha.index(c)+1<len(alpha) else 0] for c in part1)
print(f'Part 2 (index lookup loop): {time.time()-t0:.2f}s')

import binascii, random, time

alpha = 'abcdefghijklmnopqrstuvwxyz0123456789'
table = str.maketrans({c: alpha[(alpha.index(c)+1)%len(alpha)] for c in alpha})
key = 12345

def _ekyrie(text: str):
    r = ''
    for a in text:
        if a in alpha:
            a = alpha[alpha.index(a)-1]
        r += a
    return r

def _encrypt(text: str, key: int = 0):
    t = [chr(ord(t) + key) if t != '\n' else 'ζ' for t in text]
    return ''.join(t)

# 100k lines of test code (~2MB)
test_payload = 'def func_test():\n    return 42\n' * 50000

print('Encrypting test payload...')
t0 = time.time()
enc = _encrypt(_ekyrie(test_payload), key=key)
hex_content = binascii.hexlify(enc.encode('utf-8')).decode('ascii')
print(f'Encrypted in {time.time()-t0:.2f}s, hex length = {len(hex_content):,}')

# Fast decoder expression
t0 = time.time()
# 1. unhexlify
s1 = binascii.unhexlify(hex_content).decode('utf-8')
# 2. char unshift (fast bytearray/translate or ord)
s2 = ''.join(chr(ord(t)-key) if t!='ζ' else '\n' for t in s1)
# 3. alphabet unshift using dict or table
s3 = s2.translate(str.maketrans(dict(zip(alpha, alpha[1:]+alpha[:1]))))
t1 = time.time() - t0
print(f'Decoded in {t1:.2f}s! Matches: {s3 == test_payload}')

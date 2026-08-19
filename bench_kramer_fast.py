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

# Let's test a realistic 1MB payload
payload = 'x = 1\n' * 100000

t0 = time.time()
enc = _encrypt(_ekyrie(payload), key=key)
t_enc = time.time() - t0

# Kramer unhexlify + decode:
content_hex = binascii.hexlify(enc.encode('utf-8')).decode('ascii')

t0 = time.time()
# Fast Kramer decode:
raw_dec = binascii.unhexlify(content_hex).decode('utf-8')
# Fast char shift:
shifted = ''.join(chr(ord(t)-key) if t!='ζ' else '\n' for t in raw_dec)
# Fast caesar unshift:
final_code = shifted.translate(table)
t_dec = time.time() - t0

print(f'Payload size: {len(payload):,} bytes')
print(f'Encryption time: {t_enc:.4f}s')
print(f'Decryption time: {t_dec:.4f}s')
print(f'Matches perfectly: {final_code == payload}')

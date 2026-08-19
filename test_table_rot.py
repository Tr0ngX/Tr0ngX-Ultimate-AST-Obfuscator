import binascii, random

key = 12345
alpha = 'abcdefghijklmnopqrstuvwxyz0123456789'
table = str.maketrans(dict(zip(alpha, alpha[1:]+alpha[:1])))

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

orig = 'print(\"Hello world!\")\n'
enc = _encrypt(_ekyrie(orig), key=key)
content = binascii.hexlify(enc.encode('utf-8')).decode('ascii')

# Decode test:
s1 = binascii.unhexlify(content).decode('utf-8')
s2 = ''.join(chr(ord(t)-key) if t!='ζ' else '\n' for t in s1)
s3 = s2.translate(table)
print('Original:', repr(orig))
print('Decoded: ', repr(s3))
print('Matches:', orig == s3)

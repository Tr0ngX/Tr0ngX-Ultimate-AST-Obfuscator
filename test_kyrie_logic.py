content = 'print(123)\nx = 456\nprint(x)'
key = 12345
_kramer_alphabet = 'abcdefghijklmnopqrstuvwxyz0123456789'

def _ekyrie(text: str):
    r = ''
    for a in text:
        if a in _kramer_alphabet:
            a = _kramer_alphabet[_kramer_alphabet.index(a)-1]
        r += a
    return r

def _encrypt(text: str, key: int = 0):
    t = [chr(ord(t) + key) if t != '\n' else 'ζ' for t in text]
    return ''.join(t)

enc = _encrypt(_ekyrie(content), key=key)

# Decoding
def _dkyrie(enc_text, key):
    s1 = ''.join(chr(ord(t)-key) if t!='ζ' else '\n' for t in enc_text)
    _n7_ = _kramer_alphabet
    s2 = ''.join(_n7_[_n7_.index(c)+1 if _n7_.index(c)+1<len(_n7_) else 0] if c in _n7_ else c for c in s1)
    return s2

decoded = _dkyrie(enc, key)
print('Original:', repr(content))
print('Decoded: ', repr(decoded))
print('Matches:', content == decoded)

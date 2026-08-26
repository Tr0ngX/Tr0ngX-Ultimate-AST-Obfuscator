import codecs


def xor_bytes(bs, key):
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(bs))


def rot_shift(s, k):
    out = []
    for ch in s:
        if ch.isalpha() and ch.isascii():
            base = ord("a") if ch.islower() else ord("A")
            out.append(chr((ord(ch) - base + k) % 26 + base))
        else:
            out.append(ch)
    return "".join(out)


msg = "Attack at dawn! 42."
enc = rot_shift(msg, 7)
dec = rot_shift(enc, 19)
print(enc)
print(dec == msg)

payload = xor_bytes(msg.encode(), b"\x5a\xa5")
back = xor_bytes(payload, b"\x5a\xa5").decode()
print(payload.hex(" "))
print(back)
print(back == msg)
print(codecs.encode(msg, "rot13"))

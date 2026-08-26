import base64
import codecs

msg = "attack at dawn"
table = str.maketrans(
    "abcdefghijklmnopqrstuvwxyz",
    "zyxwvutsrqponmlkjihgfedcba",
)
enc = msg.translate(table)
print(enc)
print(enc.translate(table))

raw = base64.b64encode(msg.encode()).decode()
print(raw, base64.b64decode(raw).decode() == msg)
hx = codecs.encode(msg, "hex").decode()
print(hx)
rot = codecs.encode(msg, "rot_13")
print(rot)
print(bytes.fromhex(hx).decode())

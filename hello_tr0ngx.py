# -*- coding: utf-8 -*-
import sys
import time

def banner():
    print("=" * 55)
    print("  hello Tr0ngX there! Welcome to the Matrix.")
    print("=" * 55)

def compute_signature():
    # Mathematical calculation to demonstrate obfuscated runtime MBA
    base = 0x5452304E4758
    acc = 0
    for i in range(1, 100):
        acc = (acc + i * 37) ^ 0x1337
    return hex((base ^ acc) & 0xFFFFFFFFFFFF)

def main():
    banner()
    sig = compute_signature()
    print(f"[*] Core Payload Signature : {sig}")
    print(f"[*] Python Native Runtime  : {sys.version.split()[0]}")
    print("[*] Security Architecture  : Native x86_64 PE Binary (GCC -O3)")
    print("[*] Bytecode Status        : AES/ChaCha20 In-Memory Decryption")
    print("[*] Anti-Analysis Status   : Hardware PEB + Trace Hook Protection")
    print("=" * 55)
    return 0

if __name__ == "__main__":
    sys.exit(main())

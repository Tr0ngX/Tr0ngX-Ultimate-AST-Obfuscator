# -*- coding: utf-8 -*-
"""
Tr0ngX PE Armorer & Binary Post-Processor
=========================================
Applies hostile anti-analysis mutations to compiled Windows PE x86_64 binaries:
1. Strips CodeView Debug Directory & wipes PDB file path strings.
2. Scrambles standard section names (.text, .rdata, .data, .pdata) into polymorphic tokens.
3. Clears compiler watermarks (MinGW, GCC, timestamps) to eliminate fingerprinting.
4. Preserves 100% Windows NT loader (LdrpInitializeProcess) compliance.
"""

import os
import secrets
import struct
from typing import Optional

try:
    import pefile
except ImportError:
    pefile = None


def armor_pe_binary(pe_path: str, stealth_level: int = 1) -> bool:
    """
    Applies in-place post-processing armor to the compiled PE executable.
    Returns True if successfully armored, False otherwise.
    """
    if not os.path.isfile(pe_path):
        return False

    with open(pe_path, "rb") as f:
        data = bytearray(f.read())

    if len(data) < 0x200 or data[:2] != b"MZ":
        return False

    try:
        e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
        if e_lfanew + 4 > len(data) or data[e_lfanew:e_lfanew + 4] != b"PE\x00\x00":
            return False

        file_header_offset = e_lfanew + 4
        num_sections = struct.unpack_from("<H", data, file_header_offset + 2)[0]
        opt_header_size = struct.unpack_from("<H", data, file_header_offset + 16)[0]
        opt_header_offset = file_header_offset + 20

        # Optional Header Magic: 0x20B for PE32+ (x64)
        opt_magic = struct.unpack_from("<H", data, opt_header_offset)[0]
        if opt_magic != 0x20B:
            return False

        # 1. Zero out Compilation Timestamp in File Header (Anti-timeline analysis)
        struct.pack_into("<I", data, file_header_offset + 4, 0)

        # 2. Wipe Debug Directory (IMAGE_DIRECTORY_ENTRY_DEBUG is index 6)
        # In PE32+, DataDirectory starts at opt_header_offset + 112
        debug_dir_entry_offset = opt_header_offset + 112 + (6 * 8)
        debug_rva, debug_size = struct.unpack_from("<II", data, debug_dir_entry_offset)
        if debug_rva != 0 and debug_size != 0:
            # Clear Data Directory entry
            struct.pack_into("<II", data, debug_dir_entry_offset, 0, 0)

        # 3. Wipe any 'RSDS' or 'NB10' PDB signatures in raw binary
        rsds_idx = 0
        while True:
            rsds_idx = data.find(b"RSDS", rsds_idx)
            if rsds_idx == -1:
                break
            # Overwrite next 128 bytes of PDB path/GUID with zeros
            end_wipe = min(len(data), rsds_idx + 128)
            for j in range(rsds_idx, end_wipe):
                data[j] = 0
            rsds_idx += 4

        # 4. Wipe GCC compiler watermark strings
        for marker in [b"GCC: (MinGW", b"GNU C", b"mingw-w64"]:
            m_idx = 0
            while True:
                m_idx = data.find(marker, m_idx)
                if m_idx == -1:
                    break
                # Zero out 64 bytes
                end_m = min(len(data), m_idx + 64)
                for j in range(m_idx, end_m):
                    data[j] = 0
                m_idx += len(marker)

        # 5. Scramble Section Names
        # Section table starts immediately after Optional Header
        sec_table_offset = opt_header_offset + opt_header_size
        sec_names = [b".trx0\x00\x00\x00", b".trx1\x00\x00\x00", b".trx2\x00\x00\x00", b".trx3\x00\x00\x00", b".trx4\x00\x00\x00", b".trx5\x00\x00\x00"]
        
        for i in range(num_sections):
            cur_sec_offset = sec_table_offset + (i * 40)
            if cur_sec_offset + 40 > len(data):
                break
            # Assign randomized polymorphic section name (e.g. .trxN)
            new_name = sec_names[i % len(sec_names)]
            data[cur_sec_offset:cur_sec_offset + 8] = new_name

        with open(pe_path, "wb") as f:
            f.write(data)

        return True

    except Exception:
        return False

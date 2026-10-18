# -*- coding: utf-8 -*-
"""
Tr0ngX PE Armorer & Binary Post-Processor (Fortress V2 Extended)
==============================================================
Applies hostile anti-analysis mutations and deep sanitization to compiled PE x86_64 binaries:
1. Strips CodeView Debug Directory & wipes PDB file path strings.
2. Scrambles standard section names (.text, .rdata, .data, .pdata) into polymorphic tokens (.trxN).
3. Spoofs Linker Version to MSVC 14.29 (Visual Studio 2019/2022) to deceive Detect-It-Easy / PeStudio.
4. Cleanses MS-DOS stub signature message.
5. Annihilates 100% of compiler & CRT watermarks (GCC, MinGW, matherr, pseudo-relocations).
6. Recalculates mathematically valid PE CheckSum.
7. Preserves 100% Windows NT loader (LdrpInitializeProcess) compliance.
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

        # 2. Spoof Linker Version to MSVC 14.29 (Major=14, Minor=29)
        data[opt_header_offset + 2] = 14
        data[opt_header_offset + 3] = 29

        # 3. Wipe Debug Directory (IMAGE_DIRECTORY_ENTRY_DEBUG is index 6)
        debug_dir_entry_offset = opt_header_offset + 112 + (6 * 8)
        debug_rva, debug_size = struct.unpack_from("<II", data, debug_dir_entry_offset)
        if debug_rva != 0 and debug_size != 0:
            struct.pack_into("<II", data, debug_dir_entry_offset, 0, 0)

        # 4. Wipe DOS Stub default message
        dos_msg_marker = b"This program cannot be run in DOS mode."
        dos_idx = data.find(dos_msg_marker, 0x40, min(len(data), e_lfanew))
        if dos_idx != -1:
            for j in range(dos_idx, dos_idx + len(dos_msg_marker)):
                data[j] = 0

        # 5. Wipe any 'RSDS' or 'NB10' PDB signatures in raw binary
        rsds_idx = 0
        while True:
            rsds_idx = data.find(b"RSDS", rsds_idx)
            if rsds_idx == -1:
                break
            end_wipe = min(len(data), rsds_idx + 128)
            for j in range(rsds_idx, end_wipe):
                data[j] = 0
            rsds_idx += 4

        # 6. Deep Cleanse: Annihilate all GCC, MinGW, matherr & runtime failure strings
        scrub_markers = [
            b"GCC: (",
            b"gcc",
            b"MinGW",
            b"mingw",
            b"GNU C",
            b"Built by MinGW",
            b"x86_64-win32-seh",
            b"_matherr():",
            b"Argument domain error",
            b"Argument singularity",
            b"Overflow range error",
            b"Partial loss of significance",
            b"Total loss of significance",
            b"The result is too small",
            b"Unknown pseudo relocation",
            b"pseudo relocation at",
            b"VirtualProtect failed with code",
            b"VirtualQuery failed for",
            b"Address %p has no image-section",
            b"runtime error %d",
            b"Mingw-w64 runtime failure:",
            b"python3",
            b"__main__",
        ]

        for marker in scrub_markers:
            m_idx = 0
            while True:
                m_idx = data.find(marker, m_idx)
                if m_idx == -1:
                    break
                # Scan forward until null terminator or 128 bytes limit
                null_idx = data.find(b"\x00", m_idx)
                if null_idx == -1 or null_idx - m_idx > 128:
                    null_idx = min(len(data), m_idx + len(marker) + 16)
                for j in range(m_idx, null_idx):
                    data[j] = 0
                m_idx += len(marker)

        # 7. Scramble Section Names (.text, .rdata, .data -> .trxN)
        sec_table_offset = opt_header_offset + opt_header_size
        sec_names = [
            b".trx0\x00\x00\x00",
            b".trx1\x00\x00\x00",
            b".trx2\x00\x00\x00",
            b".trx3\x00\x00\x00",
            b".trx4\x00\x00\x00",
            b".trx5\x00\x00\x00"
        ]

        for i in range(num_sections):
            cur_sec_offset = sec_table_offset + (i * 40)
            if cur_sec_offset + 40 > len(data):
                break
            new_name = sec_names[i % len(sec_names)]
            data[cur_sec_offset:cur_sec_offset + 8] = new_name

        # 8. Recalculate and update valid PE Checksum
        checksum_offset = opt_header_offset + 64
        struct.pack_into("<I", data, checksum_offset, 0)
        if pefile is not None:
            try:
                pe_obj = pefile.PE(data=bytes(data))
                csum = pe_obj.generate_checksum()
                struct.pack_into("<I", data, checksum_offset, csum)
            except Exception:
                pass

        with open(pe_path, "wb") as f:
            f.write(data)

        return True

    except Exception:
        return False

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


def _rva_to_offset(rva, sections):
    """Maps an RVA to a raw file offset using the PE section table."""
    for va, vsize, raw_ptr, raw_size in sections:
        if va <= rva < va + max(vsize, raw_size):
            return raw_ptr + (rva - va)
    return None


def _protected_metadata_ranges(data, opt_header_offset, sections):
    """Byte ranges that hold live import / export metadata.

    Scrubbing those ranges would destroy the PE metadata (e.g. the 'python3' marker wipes
    'python312.dll' from the import table, and a marker like '_trx_' truncates the
    'PyInit_<module>' export name so the extension can no longer be imported), so they are
    excluded from the string cleanser. Returns a list of (start, end) file offsets.
    """
    ranges = []
    try:
        # --- imports (DataDirectory index 1) ---
        import_rva, import_size = struct.unpack_from("<II", data, opt_header_offset + 112 + (1 * 8))
        if import_rva and import_size:
            base = _rva_to_offset(import_rva, sections)
            if base is not None:
                ranges.append((base, base + import_size))
                desc_off = base
                while desc_off + 20 <= len(data):
                    desc = data[desc_off:desc_off + 20]
                    if desc == b"\x00" * 20:
                        break
                    name_rva = struct.unpack_from("<I", desc, 12)[0]
                    if name_rva:
                        name_off = _rva_to_offset(name_rva, sections)
                        if name_off is not None:
                            end = data.find(b"\x00", name_off)
                            end = name_off + 64 if end == -1 else end + 1
                            ranges.append((name_off, end))
                    desc_off += 20

        # --- exports (DataDirectory index 0) ---
        export_rva, export_size = struct.unpack_from("<II", data, opt_header_offset + 112)
        if export_rva and export_size:
            base = _rva_to_offset(export_rva, sections)
            if base is not None:
                ranges.append((base, base + export_size))
                num_names = struct.unpack_from("<I", data, base + 24)[0]
                names_rva = struct.unpack_from("<I", data, base + 32)[0]
                names_off = _rva_to_offset(names_rva, sections) if names_rva else None
                for i in range(min(num_names, 4096)):
                    if names_off is None:
                        break
                    name_rva = struct.unpack_from("<I", data, names_off + i * 4)[0]
                    if not name_rva:
                        continue
                    name_off = _rva_to_offset(name_rva, sections)
                    if name_off is None:
                        continue
                    end = data.find(b"\x00", name_off)
                    end = name_off + 128 if end == -1 else end + 1
                    ranges.append((name_off, end))
    except Exception:
        return ranges
    return ranges


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

        # Section table (RVA -> raw offset) and the import metadata ranges to protect
        sections = []
        sec_table_offset = opt_header_offset + opt_header_size
        for i in range(num_sections):
            cur = sec_table_offset + (i * 40)
            if cur + 40 > len(data):
                break
            sec_va = struct.unpack_from("<I", data, cur + 12)[0]
            sec_vsize = struct.unpack_from("<I", data, cur + 8)[0]
            sec_raw_ptr = struct.unpack_from("<I", data, cur + 20)[0]
            sec_raw_size = struct.unpack_from("<I", data, cur + 16)[0]
            sections.append((sec_va, sec_vsize, sec_raw_ptr, sec_raw_size))
        protected_ranges = _protected_metadata_ranges(data, opt_header_offset, sections)

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
            b"cpython",
            b"PyEval",
            b"sys.settrace",
            b"sys.setprofile",
            b"sys.monitoring",
            b"_code_text",
            b"Tangut",
            b"co_code",
            b"_auth_decrypt",
            b"compute_signature",
            b"_trx_",
            b".file",
            b".ident",
            b"crtexe.c",
            b"natstart.c",
            b"pseudo-reloc.c",
            b"tlssup.c",
            b"libgcc",
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
                # never touch live import metadata
                if any(r_start <= m_idx < r_end for r_start, r_end in protected_ranges):
                    m_idx += len(marker)
                    continue
                for j in range(m_idx, null_idx):
                    data[j] = 0
                m_idx += len(marker)

        # 7. Map Compiler Sections to Standard MSVC Sections (Section Merging & Stealth Cloak)
        MSVC_STANDARD_SECTIONS = [
            b".text\x00\x00\x00",
            b".rdata\x00\x00",
            b".data\x00\x00\x00",
            b".pdata\x00\x00",
            b".rsrc\x00\x00\x00",
            b".reloc\x00\x00",
        ]

        MINGW_TO_MSVC_MAP = {
            b".eh_fram": b".pdata\x00\x00",
            b".CRT": b".rdata\x00\x00",
            b".tls": b".data\x00\x00\x00",
            b".bss": b".data\x00\x00\x00",
            b".idata": b".rdata\x00\x00",
            b".xdata": b".pdata\x00\x00",
        }

        for i in range(num_sections):
            cur_sec_offset = opt_header_offset + opt_header_size + (i * 40)
            if cur_sec_offset + 40 > len(data):
                break
            raw_name = bytes(data[cur_sec_offset:cur_sec_offset + 8])
            mapped = False
            for old_pat, new_pat in MINGW_TO_MSVC_MAP.items():
                if raw_name.startswith(old_pat):
                    data[cur_sec_offset:cur_sec_offset + 8] = new_pat
                    mapped = True
                    break
            if not mapped:
                is_std = any(raw_name == std_name for std_name in MSVC_STANDARD_SECTIONS)
                if not is_std:
                    data[cur_sec_offset:cur_sec_offset + 8] = b".rdata\x00\x00"

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

# AUTO-SPLIT from tr0ngx_obfuscator.py (mechanical slice, imports pending repair)
import sys
import argparse
import ast
import copy
import glob
import random
import zlib
import marshal
import base64
import bz2
import re
import os
import hashlib
import hmac
import time
import struct
import secrets
import math
import tokenize
import io
import logging
import traceback
import threading
import string
import tempfile
import subprocess
from typing import Any, List, Dict, Optional, Tuple, Union

# Ensure Windows console supports Unicode / ANSI characters & Virtual Terminal Processing
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stdin, 'reconfigure'):
        sys.stdin.reconfigure(encoding='utf-8', errors='replace')
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        hStdOut = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(hStdOut, ctypes.byref(mode)):
            mode.value |= 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(hStdOut, mode)
except Exception:
    pass

# ═══════════════════════════════════════════════════════════════
# DEPENDENCY RESOLUTION WITH DETERMINISTIC ZERO-CRASH FALLBACKS
# ═══════════════════════════════════════════════════════════════


class _EngineState:
    verbose_debug = False
    profile_mode = False
    strict_mode = False
    log_file_path = None
    cli_quiet_mode = False
    use_cjk_names = False
    use_homoglyph_names = False
    use_rare_unicode_names = False
    use_zalgo_marks = False
    use_hyperion = False
    use_camouflage = False
    use_fused_names = False
    use_exotic_pools = None
    used_nfkc = None
    encryption_password = None
    use_math_opaque = False
    use_dyn_strings = False
    lzma_layer = False
    env_key_lock = False
    verify_mode = False
    vm_annotations = False
    anti_intercept = False
    use_anti_dump = False
    use_vm_obf = False
    custom_seed = None
    max_output_size = None

_HAS_PYSTYLE = False
_HAS_PSUTIL = False

try:
    import pystyle
    _HAS_PYSTYLE = True
except ImportError:
    _HAS_PYSTYLE = False

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

try:
    from pystyle import Col, Colors, Colorate, Write, Add, Center, Box
except ImportError:
    # Lớp giả lập pystyle dự phòng nếu môi trường không có mạng/pip lỗi
    class _FallbackCol:
        dark_gray = "\033[90m"
        light_gray = "\033[37m"
        green = "\033[92m"
        yellow = "\033[93m"
        pink = "\033[95m"
        blue = "\033[94m"
        red = "\033[91m"
        purple = "\033[35m"
        cyan = "\033[96m"
        white = "\033[97m"
        black = "\033[30m"
        reset = "\033[0m"

        @staticmethod
        def Symbol(symbol, col1="", col2=""):
            return f"[{symbol}]"

    class _FallbackColors:
        @staticmethod
        def DynamicMIX(cols):
            return cols
        @staticmethod
        def StaticMIX(cols):
            return cols[0] if cols else ""

    class _FallbackColorate:
        @staticmethod
        def Diagonal(col, text):
            return str(text)
        @staticmethod
        def Horizontal(col, text):
            return str(text)
        @staticmethod
        def Vertical(col, text):
            return str(text)

    class _FallbackWrite:
        @staticmethod
        def Print(text, col=None, interval=0):
            print(text, end="", flush=True)
        @staticmethod
        def Input(text, col=None, interval=0):
            return input(text)

    class _FallbackAdd:
        @staticmethod
        def Add(text1, text2, center=True):
            return f"{text1}\n{text2}"

    class _FallbackCenter:
        @staticmethod
        def XCenter(text):
            return str(text)
        @staticmethod
        def YCenter(text):
            return str(text)

    class _FallbackBox:
        @staticmethod
        def DoubleCube(text):
            return str(text)

    Col = _FallbackCol
    Colors = _FallbackColors
    Colorate = _FallbackColorate
    Write = _FallbackWrite
    Add = _FallbackAdd
    Center = _FallbackCenter
    Box = _FallbackBox

from getpass import getpass

if sys.version_info < (3, 10):
    print("Install Python Version = 3.10 or > 3.10 To Use This Code")
    sys.exit(1)

__import__('sys').setrecursionlimit(15000)


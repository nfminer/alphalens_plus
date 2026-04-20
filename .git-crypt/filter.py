#!/usr/bin/env python
"""Git clean/smudge filter for transparent file encryption."""
import sys
import os
from cryptography.fernet import Fernet


KEY_PATH = os.path.join(os.path.dirname(__file__), 'key')


def get_fernet():
    with open(KEY_PATH, 'rb') as f:
        key = f.read().strip()
    return Fernet(key)


def clean():
    """Encrypt plaintext from stdin to stdout (used by git add)."""
    fernet = get_fernet()
    data = sys.stdin.buffer.read()
    sys.stdout.buffer.write(fernet.encrypt(data))


def smudge():
    """Decrypt ciphertext from stdin to stdout (used by git checkout)."""
    fernet = get_fernet()
    data = sys.stdin.buffer.read()
    sys.stdout.buffer.write(fernet.decrypt(data))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'clean':
        clean()
    elif cmd == 'smudge':
        smudge()
    else:
        sys.exit(1)

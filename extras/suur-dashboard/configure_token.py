#!/usr/bin/env python3
"""Store the Things URL Scheme token outside the repository without echoing it."""

import getpass
import os
from pathlib import Path

token = getpass.getpass("Paste the Things URL token (input hidden): ").strip()
if not token:
    raise SystemExit("No token saved.")

directory = Path.home() / ".config" / "suur-things-mcp"
directory.mkdir(parents=True, mode=0o700, exist_ok=True)
directory.chmod(0o700)
path = directory / "token"
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
os.fchmod(fd, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as destination:
    destination.write(token + "\n")
print("Token saved. Refresh the SUUR dashboard; no service restart is needed.")

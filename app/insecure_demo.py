"""Intentionally insecure helper — used to demo GateKeeper blocking a PR.

Do NOT use any of this. Every function here is a deliberate SonarCloud finding.
"""

import hashlib
import os
import subprocess

# Hardcoded credential (SonarCloud: vulnerability / security hotspot).
DB_PASSWORD = "S3cr3t-Pa55word-do-not-ship"


def run(cmd: str):
    # Shell injection: untrusted string straight into a shell (vulnerability).
    return subprocess.run(cmd, shell=True, check=False)


def hash_password(password: str) -> str:
    # Weak hashing algorithm (security hotspot / vulnerability).
    return hashlib.md5(password.encode()).hexdigest()


def evaluate(expr: str):
    # Arbitrary code execution via eval (vulnerability).
    return eval(expr)  # noqa: S307


def fetch_secret() -> str:
    # Falls back to the hardcoded password above (code smell + leak).
    return os.getenv("DB_PASSWORD", DB_PASSWORD)

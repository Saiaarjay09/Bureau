"""Recovery phrases: a human-writable secondary unlock mechanism, shown
once at account creation and used later for a "forgot password" reset.

Bureau is single-user, so unlike Haven's identity-key recovery this isn't
decrypting anything — it's just a second secret that's allowed to reset
the password (see auth.reset_password_with_recovery). Reuses Haven's
2048-word BIP39 English wordlist (data/wordlist.txt) for the same reason
Haven does: it's hand-curated so no two words share a long prefix and
nothing looks similar enough to another word to cause a transcription
error when someone copies it down by hand. Only the phrase's bcrypt hash
is ever stored — see auth.py.
"""

import os
from pathlib import Path

_WORDLIST_PATH = Path(__file__).parent / "data" / "wordlist.txt"
_WORDLIST = _WORDLIST_PATH.read_text().split()
assert len(_WORDLIST) == 2048, f"expected 2048 words, found {len(_WORDLIST)}"


def generate_recovery_phrase(num_words: int = 12) -> str:
    """~11 bits of entropy per word, drawn from os.urandom (not the
    non-cryptographic `random` module) — 12 words is 132 bits."""
    indices = [int.from_bytes(os.urandom(2), "big") % len(_WORDLIST) for _ in range(num_words)]
    return " ".join(_WORDLIST[i] for i in indices)


def normalize_phrase(phrase: str) -> str:
    """Collapses whitespace and case differences so a recovery phrase
    typed back in still matches regardless of extra spaces or capitalization."""
    return " ".join(phrase.strip().lower().split())

"""Check how a spoken registration number is parsed.

Run it on the server host, in the same checkout the service runs from:

    python scripts/check_identifier.py "My FID is fifty five, sixty six, ..."

It prints what the parser normalises the sentence to, which candidate it found,
and which record it matches. If this prints the right record but the running
service still says "not found", the service is importing a different copy of
the package.
"""

from __future__ import annotations

import sys

from grm.auth.identifier import candidates, match, normalise_spoken
from grm.beneficiary360.file_backed import get_client


def main() -> int:
    text = " ".join(sys.argv[1:]).strip()
    if not text:
        print(__doc__)
        return 2

    client = get_client()
    known = client.known_identifiers()

    print(f"input      : {text}")
    print(f"normalised : {normalise_spoken(text)}")
    print(f"candidates : {candidates(text)}")
    print(f"known      : {known}")

    hit = None
    for candidate in candidates(text):
        matched = match(candidate, known)
        print(f"match      : {candidate} -> {matched}")
        hit = hit or matched

    print(f"result     : {hit or 'NO MATCH'}")
    return 0 if hit else 1


if __name__ == "__main__":
    sys.exit(main())

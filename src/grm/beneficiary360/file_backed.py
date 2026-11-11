"""File-backed client: serves Beneficiary 360 responses from local disk.

One file per person, named after their registration number:

    data/beneficiaries/FID9988776655.json

The file name is the index. Listing the directory gives every identifier the
client can resolve, without reading any record. A record is only opened when a
caller has been matched to it, so an unverified caller's data is never read from
disk.

Stands in for the live API, which the owning team supplies later. Nothing here
reaches a network. Swap this class for a real client without touching flow code,
because both satisfy `Beneficiary360Client`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from grm.beneficiary360.schemas import Beneficiary360Blob
from grm.config import DEMO_REGISTERED_MOBILE, SAMPLE_BLOB_DIR


class FileBackedBeneficiary360Client:
    """Serves one record per file, matched on the registration number."""

    def __init__(self, directory: Path | None = None) -> None:
        self._directory = directory or SAMPLE_BLOB_DIR

    def _path_for(self, identifier: str) -> Path | None:
        """Find the file whose name matches this identifier on digits alone."""
        digits = _digits(identifier)
        if not digits:
            return None
        for path in self._directory.glob("*.json"):
            if _digits(path.stem) == digits:
                return path
        return None

    def known_identifiers(self) -> tuple[str, ...]:
        """Every identifier on disk, read from file names only."""
        return tuple(sorted(path.stem for path in self._directory.glob("*.json")))

    def find_by_identifier(self, identifier: str) -> Beneficiary360Blob | None:
        """Return the record for this identifier, or None.

        Comparison is on digits only, so "FID9988776655", "FID-9988776655" and
        "9988776655" all resolve to the same file. The record is loaded only
        after a match, so a wrong number reads nothing.
        """
        path = self._path_for(identifier)
        if path is None:
            return None
        return _load_blob(path)

    def fetch_blob(self, identifier: str) -> Beneficiary360Blob:
        blob = self.find_by_identifier(identifier)
        if blob is None:
            raise ValueError(f"no record for identifier: {identifier}")
        return blob

    @property
    def foundational_id(self) -> str:
        """The default record for scripts and demos.

        With one person on disk this is unambiguous. With several, scripts
        should pass an identifier explicitly.
        """
        identifiers = self.known_identifiers()
        if not identifiers:
            raise ValueError(f"no records in {self._directory}")
        return identifiers[0]

    @property
    def registered_mobile(self) -> str:
        """Demo contact number for the default record.

        The real response carries no contact number, so the demo hardcodes one.
        A record may override it with a top-level `demo_registered_mobile` key.
        """
        blob = self.fetch_blob(self.foundational_id)
        override = (blob.model_extra or {}).get("demo_registered_mobile")
        return str(override) if override else DEMO_REGISTERED_MOBILE

    def display_name(self) -> str:
        """Best available name for the default record, without inventing one."""
        blob = self.fetch_blob(self.foundational_id)
        for registry in blob.registries:
            for register in registry.registers:
                attrs = register.attributes or {}
                first, last = attrs.get("first_name"), attrs.get("last_name")
                if first:
                    return str(first) if not last else f"{first} {last}"
        return "there"


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


@lru_cache
def _load_blob(path: Path) -> Beneficiary360Blob:
    with path.open(encoding="utf-8") as handle:
        return Beneficiary360Blob.model_validate(json.load(handle))


@lru_cache
def get_client() -> FileBackedBeneficiary360Client:
    return FileBackedBeneficiary360Client()

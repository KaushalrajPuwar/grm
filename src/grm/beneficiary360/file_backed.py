"""File-backed client: serves a Beneficiary 360 response from local disk.

Stands in for the live API, which the owning team supplies later. Nothing here
reaches a network. Swap this class for a real client without touching flow code,
because both satisfy `Beneficiary360Client`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from grm.beneficiary360.schemas import Beneficiary360Blob
from grm.config import DEMO_REGISTERED_MOBILE, SAMPLE_BLOB_PATH


class FileBackedBeneficiary360Client:
    """Serves one pre-fetched response, matched on foundational id."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or SAMPLE_BLOB_PATH
        self._blob = _load_blob(self._path)

    def fetch_blob(self, identifier: str) -> Beneficiary360Blob:
        if identifier.upper() != self.foundational_id.upper():
            raise ValueError(f"no record for identifier: {identifier}")
        return self._blob

    def find_by_identifier(self, identifier: str) -> Beneficiary360Blob | None:
        """Identifier match only.

        The response carries no contact number, so the demo OTP is routed on the
        foundational id. The live client will resolve the registered mobile from
        the auth service instead, and `find_by_identifier` will not be the path
        that releases protected data.
        """
        if identifier.strip().upper() == self.foundational_id.upper():
            return self._blob
        return None

    @property
    def foundational_id(self) -> str:
        return self._blob.beneficiary.foundationalId

    @property
    def registered_mobile(self) -> str:
        """Demo contact number. Not from the response: the real schema has none."""
        return DEMO_REGISTERED_MOBILE

    def display_name(self) -> str:
        """Best available name for greeting, without inventing one."""
        for registry in self._blob.registries:
            for register in registry.registers:
                attrs = register.attributes or {}
                first, last = attrs.get("first_name"), attrs.get("last_name")
                if first:
                    return str(first) if not last else f"{first} {last}"
        return "there"


@lru_cache
def _load_blob(path: Path) -> Beneficiary360Blob:
    with path.open(encoding="utf-8") as handle:
        return Beneficiary360Blob.model_validate(json.load(handle))


@lru_cache
def get_client() -> FileBackedBeneficiary360Client:
    return FileBackedBeneficiary360Client()

"""Client interface. File-backed and live clients both obey this."""

from __future__ import annotations

from typing import Protocol

from grm.beneficiary360.schemas import Beneficiary360Blob


class Beneficiary360Client(Protocol):
    """Read path for authenticated beneficiary and programme records."""

    #: Contact the verification code is sent to. The live API resolves this from
    #: the auth service; the file-backed demo hardcodes it because the response
    #: schema carries no mobile number.
    @property
    def registered_mobile(self) -> str: ...

    def fetch_blob(self, identifier: str) -> Beneficiary360Blob: ...

    def find_by_identifier(self, identifier: str) -> Beneficiary360Blob | None:
        """Return a snapshot only when the identifier matches a record."""
        ...

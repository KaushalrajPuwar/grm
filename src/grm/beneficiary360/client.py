"""Client interface. Real and mock both obey this."""

from typing import Protocol


class Beneficiary360Client(Protocol):
    # TODO: fetch_blob(identifier) returning BeneficiaryBlob.
    def fetch_blob(self, identifier): ...

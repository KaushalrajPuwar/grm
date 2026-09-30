"""Canned stand-in built against the real spec. Swap for real client later."""


class MockBeneficiary360Client:
    # TODO: return fixed BeneficiaryBlob fixtures per scenario.
    def fetch_blob(self, identifier):
        raise NotImplementedError

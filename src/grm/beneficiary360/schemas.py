"""Strict blob contract. JSON canonical, CSV export only."""

from pydantic import BaseModel


class BeneficiaryBlob(BaseModel):
    # TODO: beneficiary, enrolments, schemes, disbursements, grievances, meta.
    pass

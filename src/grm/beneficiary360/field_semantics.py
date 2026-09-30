"""Reading guide for Beneficiary 360 fields.

Vocabulary is scheme-specific and must not be inferred. This guide travels with
the snapshot so both the reasoning and QA agents read these fields the way the
programme means them, rather than by assuming a status code means the same thing
everywhere.
"""

FIELD_SEMANTICS = """\
`bridgeProcessing` is the live state of each benefit for the current cycle. It is
where you find out whether something is blocked and whether a delivery is
scheduled. `programs` is the durable history: enrolments per cycle and completed
disbursements. `registries` holds the profile attributes the source systems hold
about this person, including masked identity attributes.

Vocabulary worth reading carefully:

- `bridgeProcessing[].workflowType` separates a physical-goods flow (GOODS) from a
  direct money flow (CASH_DIGITAL). They fail for different reasons and mean
  different things when they do.
- `bridgeProcessing[].dispatchSchedule` appears only on GOODS benefits. If
  `deliveryStatus` is DISPATCHED_PENDING_DELIVERY then a delivery is in flight and
  `expectedDeliveryBy` is the committed date. If it is DELIVERED_TO_BENEFICIARY
  the beneficiary confirmed collection.
- `bridgeProcessing[].subsidyReleaseStatus` appears only on CASH_DIGITAL benefits.
  BLOCKED means the money is held and cannot be released.
- `bridgeProcessing[].blocker` carries the reason a release is held, and
  `resolutionOptionsAvailable` lists what can be done about it, including how
  long each option takes and whether the beneficiary has to act themselves.
- `bridgeProcessing[].workflow.fundsBlockedWithBank` is money sitting with the
  sponsor bank that has not moved. A non-zero value alongside a BLOCKED release
  or a FAILED bank dispatch is the numeric trace of the same problem.
- `bridgeProcessing[].workflow.sponsorBankDispatchStatus` is the bank leg.
  PROCESSING means the bank has not confirmed yet. FAILED means it will not
  succeed without correction.
- `bridgeProcessing[].cancellationStatus` NOT_CANCELLED means the benefit was not
  withdrawn by the beneficiary.
- `programs[].enrolments[].enrolmentStatus` ENROLLED means active on a benefit
  list. APPLIED means an application exists but entitlement is not processed.
  `entitlementProcessStatus` distinguishes the two even when status looks similar.
- `programs[].disbursements[].narrative` is written for a human. Prefer it over
  reconstructing an event from status codes alone.
- `registries[].registers[].attributes` may contain masked identity values such as
  `bank_account_masked` and short identity fragments such as `aadhaar_last4`.
  Never repeat a masked value in full. A last-four fragment that differs between
  records is meaningful evidence when you are reasoning about why a release was
  held.

A release held because the Aadhaar seeded at the bank does not match the Aadhaar
on the social registry record is a data mismatch, not a missing payment and not a
cancellation. Say which of those it is.
"""

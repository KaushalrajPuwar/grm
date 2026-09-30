"""Beneficiary 360 response contract.

Mirrors the real `Beneficiary360Response` shape. Only the fields the harness
reads directly are declared; everything else is preserved rather than dropped,
because a lossy schema would silently hide evidence the reasoning agent needs.

Field meanings are not inferred here. `field_semantics.py` carries the reading
guide, so scheme-specific vocabulary stays in one place and reaches both the
reasoning and QA agents without contaminating the transport.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SnapModel(BaseModel):
    """Permissive base. Unknown keys survive round-tripping."""

    model_config = ConfigDict(extra="allow")


class BeneficiaryRef(SnapModel):
    foundationalId: str
    matchedProgramCount: int | None = None
    matchedRegistryCount: int | None = None


class DispatchSchedule(SnapModel):
    dispatchedDate: str | None = None
    expectedDeliveryBy: str | None = None
    deliveryStatus: str
    deliveryAgentId: str | None = None
    trackingReference: str | None = None


class DisbursementRecon(SnapModel):
    remittanceReferenceNumber: str | None = None
    reversalFound: bool | None = None


class ResolutionOption(SnapModel):
    option: str
    label: str
    expectedDurationDays: int | None = None
    requiresBeneficiaryAction: bool | None = None


class Blocker(SnapModel):
    blockerCode: str
    blockerRaisedDate: str | None = None
    blockerDescription: str
    resolutionOptionsAvailable: list[ResolutionOption] = Field(default_factory=list)


class BridgeWorkflow(SnapModel):
    agencyAllocationStatus: str | None = None
    agencyMnemonic: str | None = None
    agencyNotificationStatus: str | None = None
    faResolutionStatus: str | None = None
    geoResolutionStatus: str | None = None
    warehouseAllocationStatus: str | None = None
    warehouseMnemonic: str | None = None
    warehouseNotificationStatus: str | None = None
    fundsAvailableWithBank: float | None = None
    fundsBlockedWithBank: float | None = None
    numberOfDisbursementsReconciled: int | None = None
    numberOfDisbursementsReversed: int | None = None
    numberOfDisbursementsShipped: int | None = None
    sponsorBankDispatchStatus: str | None = None
    workflowType: str | None = None


class BridgeProcessing(SnapModel):
    """One benefit's state inside the bridge, current cycle.

    This is where release blocking and dispatch scheduling are visible.
    """

    benefitCodeMnemonic: str
    benefitProgramMnemonic: str
    benefitType: str
    cancellationStatus: str | None = None
    cycleCodeMnemonic: str | None = None
    disbursementEnvelopeId: str | None = None
    totalDisbursementQuantity: float | None = None
    dispatchSchedule: DispatchSchedule | None = None
    disbursementRecon: DisbursementRecon | None = None
    subsidyReleaseStatus: str | None = None
    blocker: Blocker | None = None
    workflow: BridgeWorkflow = Field(default_factory=BridgeWorkflow)


class Enrolment(SnapModel):
    beneficiaryListId: str | None = None
    eligibilityProcessStatus: str | None = None
    enrollmentCycleId: str | None = None
    enrolmentStatus: str | None = None
    entitlementProcessStatus: str | None = None
    listDate: str | None = None
    listMnemonic: str | None = None


class Disbursement(SnapModel):
    benefitCodeMnemonic: str
    benefitType: str
    cancellationStatus: str | None = None
    cycleMnemonic: str | None = None
    disbursementCycleId: str | None = None
    disbursementDate: str | None = None
    disbursementEnvelopeId: str | None = None
    disbursementId: str | None = None
    disbursementQuantity: float | None = None
    narrative: str | None = None


class LpgConnection(SnapModel):
    """Programme-level extras the real schema does not guarantee."""

    connectionNumber: str | None = None
    connectionStatus: str | None = None
    distributorMnemonic: str | None = None
    consumerCategory: str | None = None
    subsidyEnabled: bool | None = None
    monthlySubsidyEntitlementInr: float | None = None
    annualHouseholdIncomeCeilingInr: float | None = None
    lastCollectedCylinderDate: str | None = None


class Program(SnapModel):
    disbursements: list[Disbursement] = Field(default_factory=list)
    enrolments: list[Enrolment] = Field(default_factory=list)
    lpgConnection: LpgConnection | None = None
    programId: str
    programMnemonic: str
    programName: str
    programStatus: str | None = None
    targetRegistry: str | None = None


class Register(SnapModel):
    attributes: dict[str, Any] = Field(default_factory=dict)
    foundationalId: str | None = None
    functionalRecordId: str | None = None
    internalRecordId: str | None = None
    linkFoundationalId: str | None = None
    recordStatus: str | None = None
    registerMnemonic: str | None = None
    registerName: str | None = None
    tables: list[Register] = Field(default_factory=list)


class Registry(SnapModel):
    registers: list[Register] = Field(default_factory=list)
    registryCode: str
    registryName: str | None = None
    registrySystem: dict[str, Any] | None = None


class SourceSystemWindow(SnapModel):
    system: str
    start: str | None = None
    end: str | None = None


class RequestParameters(SnapModel):
    foundationalId: str | None = None
    timeframe: str | None = None


class ResolvedTimeframe(SnapModel):
    start: str | None = None
    end: str | None = None
    perSourceSystem: list[SourceSystemWindow] = Field(default_factory=list)


class Meta(SnapModel):
    correlationId: str | None = None
    generatedAt: str | None = None
    requestParameters: RequestParameters = Field(default_factory=RequestParameters)
    resolvedTimeframe: ResolvedTimeframe = Field(default_factory=ResolvedTimeframe)
    sourceSystemsQueried: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Beneficiary360Blob(SnapModel):
    """One authenticated response. The reasoning substrate."""

    context: str | None = Field(default=None, alias="@context")
    id: str | None = Field(default=None, alias="@id")
    type: str | None = Field(default=None, alias="@type")
    beneficiary: BeneficiaryRef
    bridgeProcessing: list[BridgeProcessing] = Field(default_factory=list)
    meta: Meta = Field(default_factory=Meta)
    programs: list[Program] = Field(default_factory=list)
    registries: list[Registry] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def for_model(self) -> dict[str, Any]:
        """Plain dict for prompt embedding, with the reading guide attached."""
        from grm.beneficiary360.field_semantics import FIELD_SEMANTICS

        return {
            "response": self.model_dump(mode="json", by_alias=True),
            "how_to_read_these_fields": FIELD_SEMANTICS,
        }

    def programme(self, mnemonic: str) -> Program | None:
        return next((p for p in self.programs if p.programMnemonic == mnemonic), None)

    def bridge_entry(self, benefit_code: str) -> BridgeProcessing | None:
        return next(
            (b for b in self.bridgeProcessing if b.benefitCodeMnemonic == benefit_code), None
        )


Register.model_rebuild()

from app.models.collaboration import (
    ApprovalDecision, ClientDocumentApprovalStatus, CommentStatus, ESignatureEnvelopeStatus, ESignatureProvider,
    ESignatureSignerStatus, ReviewRequestStatus, VersionSource,
)


def test_collaboration_workflow_states_are_explicit():
    assert VersionSource.REDLINE.value == "redline"
    assert CommentStatus.RESOLVED.value == "resolved"
    assert ReviewRequestStatus.CHANGES_REQUESTED.value == "changes_requested"
    assert ApprovalDecision.APPROVED.value == "approved"


def test_esign_foundation_does_not_imply_crypto_provider():
    assert ESignatureProvider.MANUAL.value == "manual"
    assert ESignatureProvider.MOCK.value == "mock"
    assert ESignatureEnvelopeStatus.COMPLETED.value == "completed"
    assert ESignatureSignerStatus.SIGNED.value == "signed"


def test_client_approval_states_are_explicit():
    assert ClientDocumentApprovalStatus.PENDING.value == "pending"
    assert ClientDocumentApprovalStatus.CHANGES_REQUESTED.value == "changes_requested"

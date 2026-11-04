"""The file client reads only the matching beneficiary and preserves evidence."""

import json

import pytest
from pydantic import ValidationError

from grm.beneficiary360 import file_backed
from grm.beneficiary360.file_backed import FileBackedBeneficiary360Client


@pytest.fixture
def record_path(tmp_path, blob):
    path = tmp_path / "beneficiary.json"
    path.write_text(blob.model_dump_json(by_alias=True), encoding="utf-8")
    yield path
    file_backed._load_blob.cache_clear()


def test_lookup_returns_only_the_matching_beneficiary(record_path):
    client = FileBackedBeneficiary360Client(record_path)
    entered_id = " test-001\n"
    unknown_id = "TEST-002"

    matched = client.find_by_identifier(entered_id)

    assert matched is client.fetch_blob("test-001")
    assert matched.beneficiary.foundationalId == "TEST-001"
    assert client.find_by_identifier(unknown_id) is None
    with pytest.raises(ValueError, match="no record for identifier: TEST-002"):
        client.fetch_blob(unknown_id)


def test_model_context_keeps_aliases_and_extra_evidence(tmp_path):
    path = tmp_path / "extra-evidence.json"
    payload = {
        "@context": "urn:test:context",
        "@id": "urn:test:record",
        "beneficiary": {"foundationalId": "TEST-002", "customFlag": "synthetic"},
        "upstreamEvidence": {"test": True},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    client = FileBackedBeneficiary360Client(path)

    context = client.fetch_blob("TEST-002").for_model()

    record = context["response"]
    assert record["@context"] == payload["@context"]
    assert record["@id"] == payload["@id"]
    assert record["beneficiary"]["customFlag"] == "synthetic"
    assert record["upstreamEvidence"] == {"test": True}
    assert context["how_to_read_these_fields"]


@pytest.mark.parametrize(
    ("contents", "error"),
    [("invalid json", json.JSONDecodeError), ("{}", ValidationError)],
)
def test_invalid_records_raise(tmp_path, contents, error):
    path = tmp_path / "invalid.json"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(error):
        FileBackedBeneficiary360Client(path)


def test_missing_record_file_raises(tmp_path):
    missing_path = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError):
        FileBackedBeneficiary360Client(missing_path)

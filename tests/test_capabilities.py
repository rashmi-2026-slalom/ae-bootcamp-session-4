from fastapi.testclient import TestClient

from src.app import app, capabilities


client = TestClient(app)


def test_capability_filter_implementation():
    response = client.get("/capabilities?practice_area=Technology")

    assert response.status_code == 200
    payload = response.json()
    assert payload, "Expected at least one capability when filtering by Technology"

    assert set(payload.keys()) < set(capabilities.keys())
    assert all(details["practice_area"] == "Technology" for details in payload.values())


def test_capabilities_endpoint_returns_expected_shape():
    response = client.get("/capabilities")

    assert response.status_code == 200
    payload = response.json()

    assert isinstance(payload, dict)
    assert payload, "Expected capabilities endpoint to return at least one capability"

    first_capability = next(iter(payload.values()))
    assert "description" in first_capability
    assert "practice_area" in first_capability
    assert "consultants" in first_capability
    assert isinstance(first_capability["consultants"], list)

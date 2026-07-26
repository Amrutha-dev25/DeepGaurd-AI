"""Unit tests for Sightengine response parser — all known JSON schemas."""

import pytest
from app.providers.sightengine import _normalize_verdict


def test_schema_a_type_string():
    """Schema A: {"type": "deepfake", "prob": 0.98}"""
    result = _normalize_verdict({"type": "deepfake", "prob": 0.98})
    assert result["verdict"] == "fake"
    assert result["confidence"] == pytest.approx(0.98, abs=0.01)


def test_schema_b_type_dict_deepfake():
    """Schema B: {"type": {"deepfake": 0.16}}"""
    result = _normalize_verdict({"type": {"deepfake": 0.16}})
    assert result["verdict"] == "real"
    assert result["confidence"] == pytest.approx(0.84, abs=0.01)


def test_schema_c_direct_key():
    """Schema C: {"deepfake": {"prob": 0.73}}"""
    result = _normalize_verdict({"deepfake": {"prob": 0.73}})
    assert result["verdict"] == "inconclusive"
    assert 0.25 < result["confidence"] < 0.75


def test_schema_d_score_field():
    """Schema D: {"status": "success", "score": 0.91, "type": "ai_generated"}"""
    result = _normalize_verdict({"status": "success", "score": 0.91, "type": "ai_generated"})
    assert result["verdict"] == "fake"
    assert result["confidence"] == pytest.approx(0.91, abs=0.01)


def test_schema_e_overall_not_override():
    """Schema E: parser v3 uses explicit deepfake/genai keys; 'overall' is NOT a known key.
    The deepfake key (0.12) wins even though overall has a higher prob.
    """
    result = _normalize_verdict({"overall": {"prob": 0.89}, "deepfake": {"prob": 0.12}})
    assert result["verdict"] == "real"
    assert result["confidence"] == pytest.approx(0.88, abs=0.01)


def test_empty_response_returns_uncertain():
    """Empty / unknown response should not crash and return uncertain."""
    result = _normalize_verdict({"status": "success", "media": {"width": 640, "height": 480}})
    assert result["verdict"] in ("inconclusive", "real", "fake")
    assert 0.0 <= result["confidence"] <= 1.0


def test_irrelevant_model_keys_ignored():
    """Nudity/weapon keys should be excluded from score search."""
    result = _normalize_verdict({
        "weapon": {"prob": 0.99},
        "nudity": {"prob": 0.88},
        "deepfake": {"prob": 0.04},
    })
    assert result["verdict"] == "real"
    assert result["confidence"] == pytest.approx(0.96, abs=0.01)

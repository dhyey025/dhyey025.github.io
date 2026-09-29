"""Builders for valid domain objects; override only what a test cares about."""

from typing import Any

from app.models.investor import InvestorMandate
from app.models.issuer import IssuerProfile


def issuer_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "ISS-TEST",
        "company_name": "Testfield Systems Ltd",
        "ticker": None,
        "sector": "Technology",
        "region": "UK",
        "deal_size_m": 50.0,
        "revenue_m": 30.0,
        "company_stage": "growth",
        "risk_level": "medium",
    }
    payload.update(overrides)
    return payload


def mandate_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "INV-TEST",
        "investor_name": "Test Mandate Fund",
        "investor_type": "Growth Equity Fund",
        "preferred_sectors": ["Technology"],
        "preferred_regions": ["UK"],
        "min_deal_size_m": 10.0,
        "max_deal_size_m": 100.0,
        "min_revenue_m": None,
        "preferred_stages": ["growth"],
        "risk_tolerance": "medium",
        "active": True,
    }
    payload.update(overrides)
    return payload


def make_issuer(**overrides: Any) -> IssuerProfile:
    return IssuerProfile.model_validate(issuer_payload(**overrides))


def make_mandate(**overrides: Any) -> InvestorMandate:
    return InvestorMandate.model_validate(mandate_payload(**overrides))

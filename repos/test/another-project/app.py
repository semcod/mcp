"""Another sample project for E2E tests"""
from typing import Dict


def build_payload(value: int) -> Dict[str, int]:
    return {"value": value}

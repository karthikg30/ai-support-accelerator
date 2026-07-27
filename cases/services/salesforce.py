"""
Salesforce integration layer.

MVP: returns mock data so the full flow can be built and demoed
without a Salesforce sandbox.

To go live, replace `_create_case_mock` with `_create_case_live`
(OAuth + REST call). Nothing outside this file needs to change.
"""

import random
from datetime import datetime

from decouple import config

SALESFORCE_ENABLED = config('SALESFORCE_ENABLED', default=False, cast=bool)
SALESFORCE_BASE_URL = config(
    'SALESFORCE_BASE_URL', default='https://example.my.salesforce.com'
)


class SalesforceResult:
    """Uniform response shape, whether mock or live."""

    def __init__(self, success, case_number='', case_url='', error=''):
        self.success = success
        self.case_number = case_number
        self.case_url = case_url
        self.error = error


def create_salesforce_case(case):
    """Push a local Case to Salesforce. Returns a SalesforceResult."""
    if SALESFORCE_ENABLED:
        return _create_case_live(case)
    return _create_case_mock(case)


def _create_case_mock(case):
    """Fake a successful ticket creation."""
    case_number = f"{datetime.now():%y%m}{random.randint(100000, 999999)}"
    return SalesforceResult(
        success=True,
        case_number=case_number,
        case_url=f"{SALESFORCE_BASE_URL}/lightning/r/Case/{case_number}/view",
    )


def _create_case_live(case):
    """Real Salesforce REST call — implemented when credentials exist."""
    raise NotImplementedError(
        "Live Salesforce integration is not configured yet."
    )
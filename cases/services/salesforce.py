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


def create_salesforce_case(case, phi_details=''):
    """Push a local Case to Salesforce. Returns a SalesforceResult.

    `phi_details` is held in memory for the duration of this call only.
    It must never be written to the local database or to application logs.
    """
    if SALESFORCE_ENABLED:
        return _create_case_live(case, phi_details)
    return _create_case_mock(case, phi_details)


def _create_case_mock(case, phi_details=''):
    """Fake a successful ticket creation. PHI is accepted and discarded."""
    case_number = f"{datetime.now():%y%m}{random.randint(100000, 999999)}"
    return SalesforceResult(
        success=True,
        case_number=case_number,
        case_url=f"{SALESFORCE_BASE_URL}/lightning/r/Case/{case_number}/view",
    )


def _create_case_live(case, phi_details=''):
    """Real Salesforce REST call — implemented when credentials exist.

    TODO(salesforce):
      - Auth: OAuth2 client credentials (creds via .env / Key Vault)
      - Endpoint: POST /services/data/vXX.X/sobjects/Case/
      - Field mapping: pending approval from the SF team
      - PHI SAFETY: never log the request payload or the error response
        body. Log status codes and correlation IDs only.
    """
    raise NotImplementedError(
        "Live Salesforce integration is not configured yet."
    )
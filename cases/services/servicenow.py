"""
ServiceNow integration layer.

MVP: returns mock data so the full flow can be demoed without a
ServiceNow instance. Salesforce is always created first, so the
Salesforce ticket number is passed in for cross-referencing.

To go live, implement `_create_incident_live`. Nothing outside this
file needs to change.
"""

import random
from datetime import datetime

from decouple import config

SERVICENOW_ENABLED = config('SERVICENOW_ENABLED', default=False, cast=bool)
SERVICENOW_BASE_URL = config(
    'SERVICENOW_BASE_URL', default='https://example.service-now.com'
)


class ServiceNowResult:
    def __init__(self, success, ticket_number='', ticket_url='', error=''):
        self.success = success
        self.ticket_number = ticket_number
        self.ticket_url = ticket_url
        self.error = error


def create_servicenow_incident(case, phi_details='', salesforce_ticket=''):
    """Create a ServiceNow incident for a case already raised in Salesforce.

    `phi_details` is held in memory for this call only. It must never be
    written to the local database or to application logs.
    """
    if SERVICENOW_ENABLED:
        return _create_incident_live(case, phi_details, salesforce_ticket)
    return _create_incident_mock(case, phi_details, salesforce_ticket)


def _create_incident_mock(case, phi_details='', salesforce_ticket=''):
    """Fake a successful incident. PHI is accepted and discarded."""
    number = f"INC{datetime.now():%y%m}{random.randint(10000, 99999)}"
    return ServiceNowResult(
        success=True,
        ticket_number=number,
        ticket_url=(
            f"{SERVICENOW_BASE_URL}/nav_to.do"
            f"?uri=incident.do%3Fsysparm_query%3Dnumber%3D{number}"
        ),
    )


def _create_incident_live(case, phi_details='', salesforce_ticket=''):
    """Real ServiceNow REST call — implemented when credentials exist.

    TODO(servicenow):
      - Auth: OAuth2 or basic auth (creds via .env / Key Vault)
      - Endpoint: POST /api/now/table/incident
      - Field mapping (pending confirmation from the ServiceNow team):
            subject          -> short_description
            description      -> description
            priority         -> urgency / impact
            salesforce_ticket-> correlation_id or a custom reference field
      - PHI SAFETY: never log the request payload or the error response
        body. Log status codes and correlation IDs only.
    """
    raise NotImplementedError(
        "Live ServiceNow integration is not configured yet."
    )
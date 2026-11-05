"""
PHI detection guardrail.

Reference: the 18 HIPAA identifiers under the Safe Harbor de-identification
standard. Regex reliably detects the structured ones. It CANNOT detect
unstructured PHI (bare names, clinical narrative, rare conditions), so this
is a guardrail, not a guarantee. The primary control is structural: PHI
belongs in the dedicated PHI Information field, which is never sent to an LLM.
"""

import re

# ----------------------------------------------------------------------
# Patterns
# ----------------------------------------------------------------------
# Each entry: (label, compiled regex, tier)
#   'high'   — structured identifiers, very low false-positive rate
#   'medium' — useful but noisier; still blocked, listed separately so the
#              agent understands what triggered it

PATTERNS = [
    # 1-2. Names (only when explicitly labelled — bare capitalised words
    #      produce far too many false positives to be useful)
    ('Patient or member name', re.compile(
        r'\b(?:patient|member|subscriber|beneficiary|mr|mrs|ms|dr)\.?\s+'
        r'[A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20})?\b'
    ), 'medium'),

    # 3. Geographic subdivisions
    ('Street address', re.compile(
        r'\b\d{1,5}\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?\s+'
        r'(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|'
        r'Ln|Lane|Way|Ct|Court|Pl|Place)\b\.?'
    ), 'high'),

    ('ZIP code', re.compile(
        r'\b(?:zip|postal)\s*(?:code)?\s*[:#]?\s*\d{5}(?:-\d{4})?\b',
        re.IGNORECASE
    ), 'high'),

    # 4. Dates related to an individual
    ('Date of birth', re.compile(
        r'\b(?:DOB|D\.O\.B\.|date\s+of\s+birth|birth\s*date|born\s+on)\b'
        r'\s*[:#]?\s*\S+', re.IGNORECASE
    ), 'high'),

    ('Calendar date', re.compile(
        r'\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)?\d{2}\b'
    ), 'medium'),

    # 5-6. Phone and fax
    ('Phone or fax number', re.compile(
        r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
    ), 'high'),

    # 7. Email
    ('Email address', re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
    ), 'high'),

    # 8. Social Security number
    ('Social Security number', re.compile(
        r'\b(?:SSN|social\s+security)\b\s*[:#]?\s*\d{3}-?\d{2}-?\d{4}\b',
        re.IGNORECASE
    ), 'high'),

    ('Social Security number', re.compile(
        r'\b\d{3}-\d{2}-\d{4}\b'
    ), 'high'),

    # 9. Medical record number
    ('Medical record number', re.compile(
        r'\b(?:MRN|M\.R\.N\.|medical\s+record(?:\s+(?:number|no|#))?|'
        r'patient\s+(?:id|number))\b\s*[:#]?\s*[A-Z0-9][A-Z0-9-]{3,14}\b',
        re.IGNORECASE
    ), 'high'),

    # 10. Health plan beneficiary number
    ('Health plan or member ID', re.compile(
        r'\b(?:member\s*(?:id|number|#)|subscriber\s*(?:id|number|#)|'
        r'policy\s*(?:number|no|#)|group\s*(?:number|no|#)|'
        r'health\s*plan\s*id)\b\s*[:#]?\s*[A-Z0-9][A-Z0-9-]{4,19}\b',
        re.IGNORECASE
    ), 'high'),

    # 11. Account numbers
    ('Account number', re.compile(
        r'\b(?:account|acct)\s*(?:number|no|#)?\s*[:#]\s*[A-Z0-9][A-Z0-9-]{3,19}\b',
        re.IGNORECASE
    ), 'high'),

    ('Claim number', re.compile(
        r'\b(?:claim)\s*(?:number|no|#|id)?\s*[:#]\s*[A-Z0-9][A-Z0-9-]{4,19}\b',
        re.IGNORECASE
    ), 'high'),

    # 12. Certificate or licence numbers
    ('Certificate or licence number', re.compile(
        r'\b(?:licen[sc]e|certificate|NPI)\s*(?:number|no|#)?\s*[:#]?\s*'
        r'(?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{4,19}\b', re.IGNORECASE

    ), 'high'),

    # 13. Vehicle identifiers
    ('Vehicle identification number', re.compile(
        r'\b[A-HJ-NPR-Z0-9]{17}\b'
    ), 'medium'),

    # 14. Device identifiers and serial numbers
    ('Device serial number', re.compile(
        r'\b(?:serial|device)\s*(?:number|no|#|id)?\s*[:#]\s*[A-Z0-9][A-Z0-9-]{4,19}\b',
        re.IGNORECASE
    ), 'medium'),

    # 16. IP address
    ('IP address', re.compile(
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    ), 'medium'),
]

# Identifiers 15 (URLs), 17 (biometrics) and 18 (full-face photos) are not
# usefully detectable in free text. Photos are handled by keeping attachments
# out of every LLM call.


def scan(text):
    """Return a sorted list of PHI labels found in the text."""
    if not text:
        return []

    found = []
    for label, pattern, _tier in PATTERNS:
        if pattern.search(text) and label not in found:
            found.append(label)

    return sorted(found)


def contains_phi(text):
    return bool(scan(text))


def describe(labels):
    """Human-readable summary for error messages."""
    if not labels:
        return ''
    if len(labels) == 1:
        return labels[0]
    return ', '.join(labels[:-1]) + ' and ' + labels[-1]
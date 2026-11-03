"""
Product registry.

Single source of truth for product codes, display names and aliases.
Used by:
  - knowledgebase.models.product_choices()  -> admin dropdown
  - knowledgebase.models._generate_code()   -> article code prefix
  - kb_index.build_header()                 -> embedded context header
  - kb_index.expand_query()                 -> alias expansion at search time
"""

PRODUCT_REGISTRY = {
    'eCAC': {
        'name': 'Enterprise Computer-Assisted Coding',
        'aliases': ['ecac', 'Enterprise CAC', 'eCAC'],
    },
    'pCAC': {
        'name': 'Professional Computer-Assisted Coding',
        'aliases': ['PCAC', 'Professional CAC', 'pCAC'],
    },
    'OMA': {
        'name': 'Optum Market Advantage',
        'aliases': ['OMA', 'Market Advantage'],
    },
    'SPC': {
        'name': 'Surgical Profitability Compass',
        'aliases': ['SPC', 'Surgical Compass'],
    },
    'OPA': {
        'name': 'Performance Analytics Provider',
        'aliases': ['OPA', 'Performance Analytics', 'Optum Performance Analytics'],
    },
    'OCC': {
        'name': 'Optum Charge Capture',
        'aliases': ['OCC', 'Charge Capture'],
    },
    'CCC': {
        'name': 'Crimson Continuum of Care',
        'aliases': ['CCC', 'Crimson', 'Continuum of Care'],
    },
}

UNKNOWN_PRODUCT = {'name': '', 'aliases': []}

# Case-insensitive lookup: 'ECAC' / 'ecac' / 'eCAC' all resolve to 'eCAC'.
_LOOKUP = {code.upper(): code for code in PRODUCT_REGISTRY}


def canonical_code(code):
    """Return the registry's spelling of a product code, or '' if unknown."""
    key = _LOOKUP.get((code or '').strip().upper())
    return key or ''


def get_product(code):
    """Return the registry entry for a code, or a blank entry if unknown."""
    key = canonical_code(code)
    return PRODUCT_REGISTRY.get(key, UNKNOWN_PRODUCT)
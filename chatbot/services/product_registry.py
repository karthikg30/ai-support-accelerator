"""
Product registry.

Single source of truth for product names and their shorthands. Used to
build chunk headers at index time and to expand queries at search time,
so the two can never drift apart.

TODO: confirm codes, names and aliases with the real product list.
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
        'aliases': ['OCC', 'Charge Capture', ],
    },
       'CCC': {
        'name': 'Crimson Continuum of Care',
        'aliases': ['CCC', 'Crimson', 'Continuum of Care'],
    },
}

UNKNOWN_PRODUCT = {'name': '', 'aliases': []}


def get_product(code):
    return PRODUCT_REGISTRY.get((code or '').upper(), UNKNOWN_PRODUCT)
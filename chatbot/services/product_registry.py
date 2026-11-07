"""
Product registry.

Products now live in the KBProduct table (editable in Django admin).
The built-in list below is only a fallback for when the table is empty
or not migrated yet.

Used by:
  - knowledgebase.models.product_choices()  -> admin dropdown
  - knowledgebase.models._generate_code()   -> article code prefix
  - kb_index.build_header()                 -> embedded context header
  - kb_index.expand_query()                 -> alias expansion at search time
"""
from collections.abc import Mapping

_DEFAULT_REGISTRY = {
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


def get_registry():
    """Return {code: {'name': ..., 'aliases': [...]}} from the database."""
    try:
        from knowledgebase.models import KBProduct

        rows = list(KBProduct.objects.all())
    except Exception:
        rows = []

    if not rows:
        return dict(_DEFAULT_REGISTRY)

    return {
        row.code: {'name': row.name, 'aliases': row.alias_list}
        for row in rows
    }


class _LiveRegistry(Mapping):
    """Dict-like view of the registry that always reflects the database."""

    def __getitem__(self, key):
        return get_registry()[key]

    def __iter__(self):
        return iter(get_registry())

    def __len__(self):
        return len(get_registry())

    def items(self):
        return get_registry().items()

    def get(self, key, default=None):
        return get_registry().get(key, default)


PRODUCT_REGISTRY = _LiveRegistry()


def canonical_code(code):
    """Return the registry's spelling of a product code, or '' if unknown."""
    key = (code or '').strip().upper()
    for existing in get_registry():
        if existing.upper() == key:
            return existing
    return ''


def get_product(code):
    """Return the registry entry for a code, or a blank entry if unknown."""
    key = (code or '').strip().upper()
    for existing, data in get_registry().items():
        if existing.upper() == key:
            return data
    return UNKNOWN_PRODUCT
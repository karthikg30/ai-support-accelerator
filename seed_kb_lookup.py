from knowledgebase.models import KBCategory, KBProduct

CATEGORIES = [
    ('onboarding', 'Onboarding Documentation', 'ONB', 'bi-box-arrow-in-right',
     'Access requests, environment setup, and policy for new agents.', 10),
    ('user_management', 'User Management', 'UM', 'bi-person-gear',
     'Login problems, password resets, and permission provisioning.', 20),
    ('product', 'Product Articles', 'PRD', 'bi-hospital',
     'Product overviews and healthcare domain reference.', 30),
]

PRODUCTS = [
    ('eCAC', 'Enterprise Computer-Assisted Coding', 'ecac, Enterprise CAC, eCAC'),
    ('pCAC', 'Professional Computer-Assisted Coding', 'PCAC, Professional CAC, pCAC'),
    ('OMA', 'Optum Market Advantage', 'OMA, Market Advantage'),
    ('SPC', 'Surgical Profitability Compass', 'SPC, Surgical Compass'),
    ('OPA', 'Performance Analytics Provider',
     'OPA, Performance Analytics, Optum Performance Analytics'),
    ('OCC', 'Optum Charge Capture', 'OCC, Charge Capture'),
    ('CCC', 'Crimson Continuum of Care', 'CCC, Crimson, Continuum of Care'),
]

for key, label, abbrev, icon, blurb, order in CATEGORIES:
    KBCategory.objects.update_or_create(key=key, defaults={
        'label': label, 'abbrev': abbrev, 'icon': icon,
        'blurb': blurb, 'sort_order': order, 'active': True,
    })

for code, name, aliases in PRODUCTS:
    KBProduct.objects.update_or_create(code=code, defaults={
        'name': name, 'aliases': aliases, 'active': True,
    })

print('Categories:', KBCategory.objects.count(), '| Products:', KBProduct.objects.count())
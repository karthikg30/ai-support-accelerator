import os

from django import forms

from .models import Case

from chatbot.services import phi_guard

ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx',
                      '.png', '.jpg', '.jpeg', '.txt']
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB


class MultipleFileInput(forms.ClearableFileInput):
    """Allows selecting more than one file (Django's documented pattern)."""
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(d, initial) for d in data]
        return [single_clean(data, initial)]


class CaseForm(forms.ModelForm):

    includes_phi = forms.TypedChoiceField(
        label='Includes PHI Information?',
        choices=[(False, 'No'), (True, 'Yes')],
        coerce=lambda value: value == 'True',
        initial=False,
        widget=forms.RadioSelect,
    )

    attachments = MultipleFileField(required=False, label='Attachments')

    phi_details = forms.CharField(
        required=False,
        label='PHI Information',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Patient identifiers required for this case',
        }),
        help_text='Sent to Salesforce with the case. Not stored in this '
                  'application and never sent to the AI assistant.',
    )

    def clean_subject(self):
        subject = self.cleaned_data.get('subject', '')
        labels = phi_guard.scan(subject)
        if labels:
            raise forms.ValidationError(
                f'This appears to contain PHI ({phi_guard.describe(labels)}). '
                f'Move patient information into the PHI Information field.'
            )
        return subject

    def clean_description(self):
        description = self.cleaned_data.get('description', '')
        labels = phi_guard.scan(description)
        if labels:
            raise forms.ValidationError(
                f'This appears to contain PHI ({phi_guard.describe(labels)}). '
                f'Move patient information into the PHI Information field so '
                f'the description can be used with the AI assistant.'
            )
        return description

    def clean(self):
        cleaned = super().clean()
        includes_phi = cleaned.get('includes_phi')
        phi_details = (cleaned.get('phi_details') or '').strip()

        if includes_phi and not phi_details:
            self.add_error(
                'phi_details',
                'Please provide the PHI details, or set "Includes PHI" to No.'
            )

        if not includes_phi and phi_details:
            self.add_error(
                'phi_details',
                'Set "Includes PHI" to Yes to submit PHI details.'
            )

        return cleaned

    class Meta:
        model = Case
        fields = [
            'support_type', 'account_name', 'contact_name', 'priority',
            'reply_via', 'subject', 'description', 'product_request_type',
            'product_category', 'includes_phi',
        ]

        widgets = {
            'support_type': forms.Select(attrs={'class': 'form-select'}),
            'account_name': forms.Select(attrs={'class': 'form-select'}),
            'contact_name': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'reply_via': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Short summary of the issue',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'maxlength': 4000,
                'placeholder': 'Describe the issue in detail',
            }),
            'product_request_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Auto-assigned',
            }),
            'product_category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Auto-assigned',
            }),
        }

    def clean_attachments(self):
        files = self.cleaned_data.get('attachments') or []
        for f in files:
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise forms.ValidationError(
                    f"'{f.name}': file type '{ext}' is not allowed."
                )
            if f.size > MAX_FILE_SIZE:
                raise forms.ValidationError(
                    f"'{f.name}' is larger than the 25 MB limit."
                )
        return files
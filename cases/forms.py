import os

from django import forms

from .models import Case

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
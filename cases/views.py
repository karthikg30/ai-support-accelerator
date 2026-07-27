from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import CaseForm
from .models import Attachment


@login_required
def create_case(request):
    if request.method == 'POST':
        form = CaseForm(request.POST, request.FILES)
        if form.is_valid():
            case = form.save(commit=False)
            case.created_by = request.user      # never trust the form for this
            case.save()

            for uploaded_file in form.cleaned_data['attachments']:
                Attachment.objects.create(case=case, file=uploaded_file)

            messages.success(request, f'Case #{case.pk} created successfully.')
            return redirect('create_case')
    else:
        form = CaseForm()

    return render(request, 'cases/create_case.html', {'form': form})
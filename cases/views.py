from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView
from django.views.decorators.http import require_POST

from .forms import CaseForm
from .models import Attachment, Case
from .services.salesforce import create_salesforce_case


def _push_to_salesforce(case):
    """Send a case to Salesforce and record the outcome on the case."""
    result = create_salesforce_case(case)

    if result.success:
        case.salesforce_case_number = result.case_number
        case.salesforce_case_url = result.case_url
        case.sync_status = 'Synced'
        case.sync_error = ''
        case.synced_at = timezone.now()
    else:
        case.sync_status = 'Failed'
        case.sync_error = result.error

    case.save(update_fields=[
        'salesforce_case_number', 'salesforce_case_url',
        'sync_status', 'sync_error', 'synced_at',
    ])
    return result.success


@login_required
def create_case(request):
    if request.method == 'POST':
        form = CaseForm(request.POST, request.FILES)
        if form.is_valid():
            case = form.save(commit=False)
            case.created_by = request.user
            case.save()

            for uploaded_file in form.cleaned_data['attachments']:
                Attachment.objects.create(case=case, file=uploaded_file)

            if _push_to_salesforce(case):
                messages.success(
                    request,
                    f'Case created and sent to Salesforce '
                    f'(Ticket {case.salesforce_case_number}).'
                )
            else:
                messages.warning(
                    request,
                    f'Case #{case.pk} was saved locally, but the Salesforce '
                    f'sync failed. You can retry it from My Cases.'
                )
            return redirect('my_cases')
    else:
        form = CaseForm()

    return render(request, 'cases/create_case.html', {'form': form})


class MyCasesListView(LoginRequiredMixin, ListView):
    model = Case
    template_name = 'cases/my_cases.html'
    context_object_name = 'cases'
    paginate_by = 10

    def get_queryset(self):
        queryset = Case.objects.filter(created_by=self.request.user)
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(subject__icontains=query)
                | Q(account_name__icontains=query)
                | Q(salesforce_case_number__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        return context


class CaseDetailView(LoginRequiredMixin, DetailView):
    model = Case
    template_name = 'cases/case_detail.html'
    context_object_name = 'case'

    def get_queryset(self):
        # Ownership filter — prevents reading another agent's case by ID.
        return Case.objects.filter(created_by=self.request.user)


@login_required
@require_POST
def retry_sync(request, pk):
    case = get_object_or_404(Case, pk=pk, created_by=request.user)

    if case.is_synced:
        messages.info(request, 'This case is already synced.')
    elif _push_to_salesforce(case):
        messages.success(
            request,
            f'Case #{case.pk} synced (Ticket {case.salesforce_case_number}).'
        )
    else:
        messages.error(request, f'Sync failed again: {case.sync_error}')

    return redirect('my_cases')
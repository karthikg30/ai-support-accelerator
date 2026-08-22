from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView

from .forms import CaseDraftForm, CaseForm
from .models import Attachment, Case
from .services.salesforce import create_salesforce_case
from .services.servicenow import create_servicenow_incident


def _save_attachments(form, case):
    for uploaded_file in form.cleaned_data.get('attachments') or []:
        Attachment.objects.create(case=case, file=uploaded_file)


def _submit_case(case, phi_details=''):
    """Create the Salesforce case, then optionally a ServiceNow incident.

    Salesforce is the system of record and is always attempted first.
    A ServiceNow failure does not fail the submission.

    `phi_details` passes through in memory only — never written to the
    database, never included in log output.

    Returns (salesforce_ok, servicenow_ok_or_none).
    """
    sf = create_salesforce_case(case, phi_details=phi_details)

    if sf.success:
        case.salesforce_case_number = sf.case_number
        case.salesforce_case_url = sf.case_url
        case.sync_status = 'Synced'
        case.sync_error = ''
        case.synced_at = timezone.now()
    else:
        case.sync_status = 'Failed'
        case.sync_error = sf.error

    sn_ok = None
    if sf.success and case.servicenow_requested:
        sn = create_servicenow_incident(
            case,
            phi_details=phi_details,
            salesforce_ticket=case.salesforce_case_number,
        )
        sn_ok = sn.success

        if sn.success:
            case.servicenow_ticket_number = sn.ticket_number
            case.servicenow_ticket_url = sn.ticket_url
            case.servicenow_status = 'Created'
            case.servicenow_error = ''
        else:
            case.servicenow_status = 'Failed'
            case.servicenow_error = sn.error

    case.save(update_fields=[
        'salesforce_case_number', 'salesforce_case_url',
        'sync_status', 'sync_error', 'synced_at',
        'servicenow_ticket_number', 'servicenow_ticket_url',
        'servicenow_status', 'servicenow_error',
    ])

    return sf.success, sn_ok


def _handle_case_form(request, instance=None):
    if request.method == 'POST':
        is_draft = request.POST.get('action') == 'draft'
        form_class = CaseDraftForm if is_draft else CaseForm
        form = form_class(request.POST, request.FILES, instance=instance)

        if form.is_valid():
            case = form.save(commit=False)
            if case.created_by_id is None:
                case.created_by = request.user

            if is_draft:
                case.sync_status = 'Draft'
                case.save()
                _save_attachments(form, case)
                messages.success(
                    request,
                    f'Draft #{case.pk} saved. Resume it from My Cases to submit.'
                )
                return redirect('my_cases')

            case.sync_status = 'Pending'
            case.save()
            _save_attachments(form, case)

            phi_details = form.cleaned_data.get('phi_details', '')
            sf_ok, sn_ok = _submit_case(case, phi_details=phi_details)
            del phi_details

            if sf_ok and sn_ok is None:
                messages.success(
                    request,
                    f'Case submitted to Salesforce '
                    f'(Ticket {case.salesforce_case_number}).'
                )
            elif sf_ok and sn_ok:
                messages.success(
                    request,
                    f'Case submitted. Salesforce {case.salesforce_case_number}, '
                    f'ServiceNow {case.servicenow_ticket_number}.'
                )
            elif sf_ok and sn_ok is False:
                messages.warning(
                    request,
                    f'Salesforce case {case.salesforce_case_number} was created, '
                    f'but the ServiceNow incident failed. Raise it manually if '
                    f'still required.'
                )
            else:
                messages.warning(
                    request,
                    f'Case #{case.pk} was saved locally, but the Salesforce '
                    f'submission failed. PHI details were not retained and must '
                    f'be re-entered.'
                )

            return redirect('my_cases')
    else:
        form = CaseForm(instance=instance)

    return render(request, 'cases/create_case.html', {
        'form': form,
        'draft': instance,
    })


@login_required
def create_case(request):
    return _handle_case_form(request, instance=None)


@login_required
def edit_draft(request, pk):
    case = get_object_or_404(
        Case, pk=pk, created_by=request.user, sync_status='Draft'
    )
    return _handle_case_form(request, instance=case)


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
                | Q(servicenow_ticket_number__icontains=query)
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
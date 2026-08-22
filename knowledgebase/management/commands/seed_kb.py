from django.core.management.base import BaseCommand

from knowledgebase.models import KnowledgeArticle

ARTICLES = [
    # ---------- Onboarding Documentation ----------
    {
        'code': 'KB2001',
        'category': 'onboarding',
        'title': 'Salesforce Access for New Users',
        'summary': 'How to request, approve, and verify Salesforce access for a new support agent.',
        'content': """Use this procedure when a new agent joins the Tier-1 team and needs Salesforce case access.

Before you start:
- Confirm the agent's employee ID and manager approval are on record.
- Confirm which support queue the agent will work in.

Steps:
1. Raise an access request through the internal access portal, selecting the Salesforce Support Console profile.
2. Attach manager approval to the request. Requests without approval are rejected automatically.
3. Select the permission set matching the agent's tier. Tier-1 agents receive read and create rights on Case, and read-only on Account and Contact.
4. Wait for provisioning. Standard turnaround is one to two business days.
5. Ask the agent to sign in and confirm they can open the Support Console and create a test case in the training queue.
6. If sign-in fails with an authentication error, confirm the agent's SSO account is active before raising a new request.

Common issues:
- Access granted but console not visible: the profile was applied without the console permission set. Raise an amendment rather than a new request.
- Agent sees cases from other queues: queue membership is separate from profile. Request a queue correction.

Escalate to the Salesforce administration team if provisioning exceeds three business days.""",
    },
    {
        'code': 'KB2002',
        'category': 'onboarding',
        'title': 'ServiceNow Access for New Users',
        'summary': 'Requesting ServiceNow access and the correct fulfiller group for support staff.',
        'content': """Use this procedure to grant a new agent access to ServiceNow for incident and request handling.

Before you start:
- Confirm the agent has completed mandatory security training. Access is blocked until this is recorded.
- Identify the fulfiller group the agent belongs to.

Steps:
1. Submit a ServiceNow access request specifying the ITIL fulfiller role, not the standard requester role. Requester access cannot work incidents.
2. Specify the assignment group so incidents route to the agent's queue.
3. Confirm whether the agent needs knowledge base authoring rights. This is a separate role and is not granted by default.
4. Once provisioned, ask the agent to sign in and confirm they can view their assignment group's incident list.
5. Ask the agent to update their notification preferences so queue assignments generate an email.

Common issues:
- Agent can log in but sees no incidents: almost always missing assignment group membership rather than a role problem.
- Agent cannot resolve incidents: the ITIL role was not applied; a requester role allows viewing only.

Escalate to the ServiceNow platform team if the fulfiller role is not applied within two business days.""",
    },
    {
        'code': 'KB2003',
        'category': 'onboarding',
        'title': 'New Agent Setup Checklist',
        'summary': 'End-to-end checklist covering everything a Tier-1 agent needs on day one.',
        'content': """Work through this checklist in order. Items later in the list depend on earlier ones.

Identity and network:
1. Corporate account created and password set.
2. Multi-factor authentication registered on the agent's device.
3. VPN client installed and a successful test connection completed.

Core tools:
4. Salesforce access provisioned and verified (see KB2001).
5. ServiceNow access provisioned and verified (see KB2002).
6. Support Accelerator AI account created and the agent added to the correct group.
7. Telephony or softphone configured and a test call completed.

Knowledge and policy:
8. PHI and security policy acknowledged (see KB2005).
9. Product familiarisation completed for the products in the agent's queue.
10. Shadowing sessions scheduled with an experienced agent.

Verification:
11. Agent creates a test case end to end in the training queue.
12. Manager confirms the agent can locate, classify, and escalate a case correctly.

Do not release an agent to live queues until item 12 is complete.""",
    },
    {
        'code': 'KB2004',
        'category': 'onboarding',
        'title': 'VPN and Remote Access Setup',
        'summary': 'Installing the VPN client and resolving the most common connection failures.',
        'content': """Most internal applications are unreachable without an active VPN session. Complete this before troubleshooting any application access problem.

Setup:
1. Install the approved VPN client from the software portal. Do not use a personally downloaded build.
2. Sign in with the corporate account and complete the MFA prompt.
3. Confirm the connection shows as active and the assigned internal address is populated.
4. Open an internal-only page to confirm routing works.

Common failures:
- Authentication succeeds but no internal access: the tunnel connected without routes. Disconnect, reconnect, and confirm the assigned address changes.
- MFA prompt never arrives: the registered device is stale. Re-register the device before retrying.
- Connection drops repeatedly on home networks: usually a local network issue. Test on a different network before raising a ticket.
- Client refuses to start after an operating system update: reinstall from the software portal.

Before escalating, capture the exact error text, the timestamp, and whether the failure reproduces on a different network.""",
    },
    {
        'code': 'KB2005',
        'category': 'onboarding',
        'title': 'PHI and Security Policy for Support Agents',
        'summary': 'What counts as PHI, where it may be recorded, and what to do if it is exposed.',
        'content': """Protected Health Information must be handled with care in every support interaction. Read this before working live cases.

What counts as PHI:
Any information that identifies an individual and relates to their health, care, or payment for care. This includes names, dates of birth, addresses, phone numbers, email addresses, medical record numbers, member and subscriber identifiers, account and claim numbers, and device identifiers.

Where PHI may be recorded:
1. Only in the dedicated PHI field of a support case, and only when genuinely required to resolve the issue.
2. Never in the case subject or description. These fields are used with AI assistance and must remain free of patient information.
3. Never in a chat message to the AI assistant.
4. Never in email, instant messages, or personal notes.

Minimum necessary principle:
Record only the identifiers actually needed. If a case can be resolved with an account reference alone, do not record patient details.

If PHI is exposed:
1. Stop. Do not forward, copy, or continue the conversation.
2. Report through the incident reporting procedure immediately.
3. Notify the Privacy Office without delay.
4. Preserve the evidence. Do not delete the message or case.

Reporting a suspected exposure promptly is always the correct action and is never penalised.""",
    },

    # ---------- User Management ----------
    {
        'code': 'KB1001',
        'category': 'user_management',
        'title': 'Portal Login Troubleshooting',
        'summary': 'Step-by-step diagnosis for a user who cannot sign in to the portal.',
        'content': """Use this procedure when a user reports being unable to sign in to the portal.

Diagnosis order:
1. Verify account status. Confirm the account is active and not locked, expired, or pending activation.
2. Clear browser cache and cookies, then retry in a private or incognito window. This resolves a significant share of reported login failures.
3. Confirm the user is on a supported browser and version.
4. Verify VPN connectivity if the user is accessing internally (see KB2004).
5. Check the outage dashboard for active incidents affecting authentication.
6. Confirm the user is entering the correct username. Email address and username are not always identical.

If the account is locked:
Follow the account lockout procedure in KB1013.

If the password has expired:
Follow the password reset procedure in KB1010.

Before escalating, collect:
- The exact error message and the time it occurred
- Whether the failure reproduces in a private window
- Whether other users at the same site are affected
- The browser and operating system version

Escalate to Tier 2 if the account is confirmed active, no outage is in progress, and the failure reproduces across browsers.""",
    },
    {
        'code': 'KB1002',
        'category': 'user_management',
        'title': 'Browser Cache and Session Issues',
        'summary': 'Recognising and resolving stale session problems that mimic access failures.',
        'content': """Stale browser state produces symptoms that look like access or permission problems. Rule this out early.

Typical symptoms:
- Pages load partially or show outdated content
- A spinner that never resolves
- Permission errors immediately after a role change
- The user is signed in but repeatedly redirected to the login page

Resolution:
1. Ask the user to retry in a private or incognito window. If the problem disappears, it is cached state.
2. Clear cookies and cached files for the application domain specifically rather than the entire browser history.
3. Sign out fully and sign back in, rather than simply closing the tab.
4. If the user recently had a permission change, the old session may still carry the previous rights. A full sign-out and sign-in refreshes them.
5. Disable browser extensions temporarily. Ad blockers and privacy extensions can interfere with authentication flows.

When it is not cache:
If the problem reproduces in a private window on a different machine, stop treating it as a cache issue and continue with KB1001.

Note for the case record:
Record whether a private window resolved the issue. This single detail saves Tier 2 significant time.""",
    },
    {
        'code': 'KB1010',
        'category': 'user_management',
        'title': 'Password Reset Procedure',
        'summary': 'Verifying identity and issuing a password reset safely.',
        'content': """Follow this procedure whenever a user requests a password reset. Identity verification is mandatory and must not be skipped under time pressure.

Steps:
1. Verify the caller's identity according to the verification policy for their account type. Do not proceed without successful verification.
2. Confirm the account exists and note whether it is active, locked, or expired.
3. Trigger the password reset from the administration console. Do not set a password on the user's behalf.
4. Confirm the reset notification has been sent to the address on record. If the address is wrong, this becomes an account update request rather than a reset.
5. Ask the user to complete the reset and confirm they can sign in.
6. If the account was also locked, unlock it after the reset completes (see KB1013).

Do not:
- Read a temporary password aloud over an unrecorded channel
- Reset a password based on an email request alone without verification
- Bypass verification because the caller is known to you

Common issues:
- Reset email not received: check junk folders first, then confirm the address on record, then check whether notifications are suppressed for that domain.
- Reset link expired: links are time-limited. Issue a new one rather than extending the old.

Record in the case that verification was completed, without recording the verification answers.""",
    },
    {
        'code': 'KB1011',
        'category': 'user_management',
        'title': 'MFA Device Re-registration',
        'summary': 'Re-registering multi-factor authentication after a device change or loss.',
        'content': """Use this procedure when a user cannot complete multi-factor authentication because their registered device has changed, been replaced, or been lost.

Before you start:
Identity verification is mandatory. MFA re-registration is a high-risk action and is a common target for social engineering. Verify carefully.

Steps:
1. Verify the caller's identity to the enhanced standard required for MFA changes.
2. Confirm the reason for re-registration and note whether the previous device was lost or simply replaced.
3. If the device was lost or stolen, revoke the existing registration immediately before issuing a new one.
4. Remove the old registration from the account.
5. Issue a re-registration link or temporary access code according to policy.
6. Guide the user through registering the new device.
7. Ask the user to sign out fully and sign in again to confirm the new factor works.

If the device was lost or stolen:
Treat this as a potential security event. Revoke the registration first, then follow the security reporting procedure in KB2005.

Do not:
- Disable MFA on the account as a workaround
- Re-register a device on the basis of an email request alone

Escalate to the identity team if the account shows repeated failed re-registration attempts, which may indicate an attack in progress.""",
    },
    {
        'code': 'KB1012',
        'category': 'user_management',
        'title': 'Permission Provisioning for Client Users',
        'summary': 'Granting, changing, and verifying permissions for client-side users.',
        'content': """Use this procedure when a client requests new or changed permissions for one of their users.

Before you start:
- Confirm the request comes from an authorised contact at the client. Permission changes requested by the end user themselves are not sufficient.
- Confirm which product and environment the change applies to.

Steps:
1. Identify the user's current role and permission set. Record it before making changes so it can be reverted.
2. Confirm the requested permission against the client's approved role matrix. If the request falls outside the matrix, it needs client administrator approval.
3. Apply the change using role assignment rather than individual permission grants where possible. Individual grants are difficult to audit and reproduce.
4. Ask the user to sign out fully and sign in again. Permission changes do not take effect in an existing session (see KB1002).
5. Ask the user to confirm they can perform the intended action and, importantly, that no unintended access appeared.
6. Record in the case what was changed, by whose authority, and when.

Applying the principle of least privilege:
Grant the narrowest permission that accomplishes the stated need. If a client requests broad administrative rights for a narrow task, propose the narrower role and explain why.

Escalate if:
- The requested permission would grant access to another client's data
- The request would give a user both creation and approval rights in the same workflow""",
    },
    {
        'code': 'KB1013',
        'category': 'user_management',
        'title': 'Account Lockout and Reactivation',
        'summary': 'Unlocking accounts safely and identifying lockouts that indicate an attack.',
        'content': """Accounts lock automatically after repeated failed sign-in attempts. Most lockouts are benign, but some indicate an attack in progress.

Steps:
1. Verify the caller's identity before taking any action.
2. Check the lockout reason and the number and timing of failed attempts.
3. Check whether the failed attempts originated from the user's usual location and device.
4. If the pattern is consistent with the user simply mistyping a password, unlock the account.
5. Ask the user to sign in and confirm access.
6. If the password is also expired or forgotten, complete the reset first (see KB1010), then unlock.

When a lockout is a security signal:
Treat the lockout as suspicious and escalate rather than unlocking if any of the following apply:
- Failed attempts came from an unfamiliar location or country
- A large number of attempts occurred in a short window
- Multiple accounts at the same client locked at the same time
- The user reports they were not attempting to sign in

In these cases, leave the account locked, do not reset the password, and escalate to the security team immediately.

Repeated lockouts for one user:
If the same account locks repeatedly, the cause is often a saved credential on a secondary device or a service still using an old password. Check mobile devices and mail clients before assuming user error.""",
    },

    # ---------- Product Articles ----------
    {
        'code': 'KB3001',
        'category': 'product',
        'title': 'Enterprise Computer-Assisted Coding Overview',
        'summary': 'What Enterprise CAC does, who uses it, and the issues support sees most often.',
        'content': """Enterprise Computer-Assisted Coding accounts for the largest share of Tier-1 support volume. A working understanding of the product shortens most cases.

What it does:
The product reads clinical documentation and suggests medical codes for coders to review. Natural language processing extracts clinical concepts from notes, maps them to code sets, and presents suggestions with supporting evidence from the document. A human coder reviews, accepts, amends, or rejects each suggestion.

Who uses it:
Inpatient and outpatient coding teams at hospitals and health systems, typically working through a queue of encounters.

Where support fits:
The product is used continuously during a coder's working day, so access and availability problems have immediate operational impact. Prioritise accordingly.

Common issue categories:
1. User access and permissions, which is the largest category by volume.
2. Documents not appearing in the work queue, usually an interface or feed problem rather than a product fault (see KB3004).
3. Code suggestions absent or incomplete for a particular encounter, often because the source document did not arrive in full.
4. Performance degradation during peak coding hours.
5. Site configuration questions relating to queue routing and worklist rules.

Useful questions to ask:
- Is the issue affecting one coder, one facility, or all users?
- Does the affected encounter appear in the source system?
- When did the behaviour start, and did anything change at that time?""",
    },
    {
        'code': 'KB3002',
        'category': 'product',
        'title': 'Professional CAC and Coding Workflows',
        'summary': 'How the professional-fee product differs from the enterprise product.',
        'content': """Professional Computer-Assisted Coding supports professional-fee coding, which differs meaningfully from the facility coding supported by the enterprise product.

Key difference:
Facility coding captures the resources a hospital used to deliver care. Professional coding captures the work performed by an individual clinician. The same encounter can generate both, coded separately by different teams using different rules.

What this means for support:
1. Do not assume a workflow question has the same answer across both products. Queue behaviour, code sets, and validation rules differ.
2. Confirm which product the user is working in before troubleshooting. Users at organisations running both will not always say.
3. Escalation paths differ between the two products.

Common issue categories:
- Provider attribution, where work is assigned to the wrong clinician
- Encounter routing between professional and facility queues
- Code set version questions following an annual update
- Access separation, where a coder needs one product but not the other

When taking the case:
Record the product name explicitly rather than writing "CAC". The distinction matters to Tier 2 and is frequently lost at handoff.""",
    },
    {
        'code': 'KB3003',
        'category': 'product',
        'title': 'Clinical Documentation Improvement Basics',
        'summary': 'What CDI teams do and why their queries appear in support cases.',
        'content': """Clinical Documentation Improvement, usually shortened to CDI, aims to make clinical documentation accurately reflect the care a patient received.

Why it exists:
Coding can only capture what is documented. If documentation is ambiguous, incomplete, or inconsistent, the resulting codes will not reflect the patient's actual condition or the resources used. This affects quality reporting, reimbursement accuracy, and severity measurement.

What CDI specialists do:
They review records while a patient is still admitted, identify gaps or ambiguities, and issue a query to the treating clinician asking for clarification. A query never suggests a diagnosis; it asks the clinician to clarify what they observed and concluded.

Where support sees CDI:
1. Queries not reaching the intended clinician
2. Worklist prioritisation questions, since CDI teams work by risk and length of stay rather than in arrival order
3. Integration questions between CDI review and the coding workflow
4. Reporting questions on query response rates and agreement rates

Terminology you will encounter:
- Query: a request to a clinician for documentation clarification
- Response rate: the share of queries a clinician answers
- Agreement rate: the share of answered queries that result in a documentation change

Note for case handling:
CDI cases often have time pressure attached, because a query is far less useful after the patient is discharged. Ask whether the patient is still admitted.""",
    },
    {
        'code': 'KB3004',
        'category': 'product',
        'title': 'HL7 Interfaces and Feed Failures',
        'summary': 'Diagnosing missing data caused by interface problems rather than product faults.',
        'content': """Most reports of missing documents, missing encounters, or stale data are interface problems rather than faults in the product the user is looking at.

What an interface does:
Clinical systems exchange data using HL7 messages. A feed carries messages from a source system into the product. If the feed stops, slows, or rejects messages, the product simply has nothing to display, and the user experiences this as a product fault.

Recognising an interface problem:
1. Data is missing rather than wrong. The record is absent, not incorrect.
2. The gap has a clear start time, after which nothing arrived.
3. Multiple users at the same site are affected, while other sites are unaffected.
4. The record exists in the source system but not in the product.

Diagnostic questions:
- Does the encounter exist in the source system?
- What is the timestamp of the most recent record that did arrive?
- Is the gap limited to one message type, or is everything missing?
- Did anything change at the site recently, such as an upgrade or a network change?

What to capture before escalating:
The facility identifier, the affected message type if known, the timestamp of the last successful record, and at least one specific example of a record that should have arrived. An interface escalation without a concrete example is usually returned for more detail.

Do not:
Attempt to re-send or replay messages. Message replay is handled by the interface team and can create duplicates if done incorrectly.""",
    },
    {
        'code': 'KB3005',
        'category': 'product',
        'title': 'Optum Market Advantage Overview',
        'summary': 'What the product provides and the support issues associated with it.',
        'content': """Optum Market Advantage is the second largest product by Tier-1 support volume.

What it does:
The product provides market and performance intelligence to help health systems understand referral patterns, market share, provider networks, and service line performance. Users are typically strategy, planning, and network development teams rather than clinical staff.

How the user profile changes support:
1. Usage is periodic rather than continuous. Users often work intensively around planning cycles and then not at all for weeks.
2. Because usage is intermittent, access problems frequently surface after a long gap, when passwords have expired or accounts have been deactivated for inactivity.
3. Users are analytically sophisticated but may be unfamiliar with the application itself, so questions are often about interpretation rather than faults.

Common issue categories:
- Account reactivation after a period of inactivity
- Data refresh timing questions, particularly around when a reporting period becomes available
- Report export problems, especially with large extracts
- Questions about methodology and data sources, which usually need routing rather than troubleshooting

Routing guidance:
Distinguish carefully between a fault and a question. A user asking how a metric is derived needs a subject matter expert, not a technical escalation. Misrouting these wastes a full escalation cycle.""",
    },
    {
        'code': 'KB3006',
        'category': 'product',
        'title': 'Coding and Reimbursement Fundamentals',
        'summary': 'Core terminology and concepts that appear throughout support cases.',
        'content': """This article covers terminology that appears constantly in support cases. Understanding it helps you classify and describe cases accurately.

Code sets:
- ICD-10-CM records diagnoses, describing the patient's conditions.
- ICD-10-PCS records inpatient procedures.
- CPT records outpatient and professional procedures and services.
- HCPCS records supplies, drugs, and services outside CPT.

Grouping and payment:
Codes are grouped to determine payment. In the inpatient setting, diagnoses and procedures group into a DRG, which determines the payment amount for the admission. Secondary diagnoses can change the grouping when they represent genuine additional complexity.

Two terms you will see frequently:
- CC, a complication or comorbidity, which increases the severity of a stay.
- MCC, a major complication or comorbidity, which increases it further.

Why documentation matters:
A condition that is present but not documented cannot be coded, and therefore does not affect grouping. This is the core reason CDI exists (see KB3003).

The annual update cycle:
Code sets are revised annually. Support volume rises predictably around each update, with questions about new codes, retired codes, and mapping between versions. Expect this and check whether a reported problem coincides with an update.

Using this in case handling:
Recording the correct code set and setting in the case description saves a clarification cycle. "CPT code question, outpatient" is far more useful to Tier 2 than "coding issue".""",
    },
]


class Command(BaseCommand):
    help = 'Seed the knowledge base with demo articles.'

    def handle(self, *args, **options):
        created = 0
        updated = 0

        for data in ARTICLES:
            obj, was_created = KnowledgeArticle.objects.update_or_create(
                code=data['code'],
                defaults={
                    'title': data['title'],
                    'category': data['category'],
                    'summary': data['summary'],
                    'content': data['content'],
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Knowledge base seeded: {created} created, {updated} updated.'
        ))
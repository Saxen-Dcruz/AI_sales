import ApplicationStore from "../utils/ApplicationStore";

const successCaseCode = [200, 201];

const _fetchService = (PATH, serviceMethod, data, successCallback, errorCallBack) => {
    const { accessToken, userDetails } = ApplicationStore().getStorage("userDetails") || {};
    const END_POINT = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1/';

    if (!userDetails) {
        return Promise.reject("Unauthorized: No user details found.");
    }
    const { id, email, userRole, companyCode, semesterId } = userDetails;

    const isFormData = data instanceof FormData;

    const authHeaders = {
        authorization: `Bearer ${accessToken}`,
        companyCode: `${companyCode}`,
        userId: `${id}`,
        userEmail: `${email}`,
        userRole: `${userRole}`,
        semesterId: `${semesterId}`,
        branch: `${userDetails.branch}`,
        instituteid: `${userDetails.instituteid}`,
    };

    const headers = isFormData
        ? authHeaders
        : { "Content-Type": "application/json", ...authHeaders };

    const requestOptions = {
        method: serviceMethod,
        headers,
        body:
            serviceMethod === "GET" || serviceMethod === "DELETE"
                ? undefined
                : isFormData
                    ? data
                    : JSON.stringify(data),
        mode: "cors",
        cache: "no-cache",
        credentials: "same-origin",
        redirect: "follow",
        referrerPolicy: "no-referrer",
    };

    return fetch(END_POINT + PATH, requestOptions)
        .then((response) => {
            if (successCaseCode.includes(response.status)) {
                return response.json();
            }
            throw {
                errorStatus: response.status,
                errorObject: response.json(),
            };
        })
        .then((dataResponse) => successCallback(dataResponse))
        .catch((error) => {
            if (error?.errorObject?.then) {
                error.errorObject.then((errorResponse) => {
                    if (error.errorStatus === 400 && errorResponse.message === "Token is required") {
                        ApplicationStore().clearStorage();
                    }
                    errorCallBack && errorCallBack(error.errorStatus, errorResponse.message);
                });
            } else {
                errorCallBack && errorCallBack(500, String(error));
            }
        });
};

// ── Auth ──────────────────────────────────────────────────────────────────────

export const LoginService = (data) => {
    const PATH = 'auth/login';
    const END_POINT = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1/';
    return fetch(END_POINT + PATH, {
        method: 'POST',
        mode: 'cors',
        cache: 'no-cache',
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        redirect: 'follow',
        referrerPolicy: 'no-referrer',
        body: JSON.stringify(data),
    });
};

export const LogoutService = (data, success, error) =>
    _fetchService('auth/logout', 'POST', data, success, error);

export const GetCurrentUserService = (success, error) =>
    _fetchService('auth/me', 'GET', null, success, error);

// ── Products ──────────────────────────────────────────────────────────────────

export const AddProductService = (data, success, error) =>
    _fetchService('products/', 'POST', data, success, error);

export const ShowAllProductService = (data, success, error) =>
    _fetchService('products/', 'GET', data, success, error);

export const ShowOneProductService = (data, success, error) =>
    _fetchService(`products/${data.id}`, 'GET', null, success, error);

// Fixed: PUT → PATCH (backend uses PATCH for partial updates)
export const EditProductService = (id, data, success, error) =>
    _fetchService(`products/${id}`, 'PATCH', data, success, error);

export const DeleteProductService = (id, success, error) =>
    _fetchService(`products/${id}`, 'DELETE', null, success, error);

// Fixed: correct availability endpoint
export const ToggleActiveInactiveService = (id, success, error) =>
    _fetchService(`products/${id}/availability`, 'PATCH', null, success, error);

// ── Dashboard ─────────────────────────────────────────────────────────────────

export const GetDashboardSummaryService = (success, error) =>
    _fetchService('dashboard/summary', 'GET', null, success, error);

// ── Leads ─────────────────────────────────────────────────────────────────────

export const GetLeadsService = (params = {}, success, error) => {
    const qs = new URLSearchParams();
    if (params.page)           qs.set('page', params.page);
    if (params.limit)          qs.set('limit', params.limit);
    if (params.search)         qs.set('search', params.search);
    if (params.status)         qs.set('status', params.status);
    if (params.classification) qs.set('classification', params.classification);
    if (params.at_risk)        qs.set('at_risk', 'true');
    const query = qs.toString();
    return _fetchService(`leads/${query ? '?' + query : ''}`, 'GET', null, success, error);
};

export const GetLeadService = (id, success, error) =>
    _fetchService(`leads/${id}`, 'GET', null, success, error);

export const CreateLeadService = (data, success, error) =>
    _fetchService('leads/', 'POST', data, success, error);

export const UpdateLeadService = (id, data, success, error) =>
    _fetchService(`leads/${id}`, 'PATCH', data, success, error);

export const DeleteLeadService = (id, success, error) =>
    _fetchService(`leads/${id}`, 'DELETE', null, success, error);

export const GetLeadScoreBreakdownService = (id, success, error) =>
    _fetchService(`leads/${id}/score-breakdown`, 'GET', null, success, error);

export const ReclassifyLeadService = (id, success, error) =>
    _fetchService(`leads/${id}/reclassify`, 'POST', null, success, error);

export const GetLeadSentimentTimelineService = (id, success, error) =>
    _fetchService(`leads/${id}/sentiment-timeline`, 'GET', null, success, error);

export const GetClassificationSummaryService = (success, error) =>
    _fetchService('leads/classification-summary', 'GET', null, success, error);

// ── Deals ─────────────────────────────────────────────────────────────────────

export const GetDealsService = (params = {}, success, error) => {
    const qs = new URLSearchParams();
    if (params.page)       qs.set('page', params.page);
    if (params.limit)      qs.set('limit', params.limit);
    if (params.stage)      qs.set('stage', params.stage);
    if (params.company_id) qs.set('company_id', params.company_id);
    if (params.at_risk)    qs.set('at_risk', 'true');
    const query = qs.toString();
    return _fetchService(`deals/${query ? '?' + query : ''}`, 'GET', null, success, error);
};

export const CreateDealService = (data, success, error) =>
    _fetchService('deals/', 'POST', data, success, error);

export const UpdateDealService = (id, data, success, error) =>
    _fetchService(`deals/${id}`, 'PATCH', data, success, error);

export const DeleteDealService = (id, success, error) =>
    _fetchService(`deals/${id}`, 'DELETE', null, success, error);

// ── Calls ─────────────────────────────────────────────────────────────────────

export const GetCallAnalyticsService = (success, error) =>
    _fetchService('calls/analytics', 'GET', null, success, error);

export const GetCallsService = (params = {}, success, error) => {
    const qs = new URLSearchParams();
    if (params.page)      qs.set('page', params.page);
    if (params.limit)     qs.set('limit', params.limit);
    if (params.direction) qs.set('direction', params.direction);
    if (params.status)    qs.set('status', params.status);
    if (params.outcome)   qs.set('outcome', params.outcome);
    if (params.lead_id)   qs.set('lead_id', params.lead_id);
    const query = qs.toString();
    return _fetchService(`calls/${query ? '?' + query : ''}`, 'GET', null, success, error);
};

export const GetCallService = (id, success, error) =>
    _fetchService(`calls/${id}`, 'GET', null, success, error);

export const GetCallGapsService = (success, error) =>
    _fetchService('calls/gaps', 'GET', null, success, error);

export const SubmitCallTranscriptService = (id, data, success, error) =>
    _fetchService(`calls/${id}/transcript`, 'POST', data, success, error);

export const ResolveCallGapService = (id, data, success, error) =>
    _fetchService(`calls/${id}/gaps/resolve`, 'POST', data, success, error);

// ── Gmail ─────────────────────────────────────────────────────────────────────

export const GetEmailsService = (params = {}, success, error) => {
    const qs = new URLSearchParams();
    if (params.page)         qs.set('page', params.page);
    if (params.limit)        qs.set('limit', params.limit);
    if (params.label)        qs.set('label', params.label);
    if (params.status)       qs.set('status', params.status);
    if (params.needs_human)  qs.set('needs_human', 'true');
    const query = qs.toString();
    return _fetchService(`gmail/${query ? '?' + query : ''}`, 'GET', null, success, error);
};

export const SyncGmailService = (success, error) =>
    _fetchService('gmail/sync', 'POST', {}, success, error);

export const GetEmailGapsService = (success, error) =>
    _fetchService('gmail/gaps', 'GET', null, success, error);

export const ResolveEmailGapService = (id, data, success, error) =>
    _fetchService(`gmail/${id}/gaps/resolve`, 'POST', data, success, error);

export const ApproveDraftService = (id, data, success, error) =>
    _fetchService(`gmail/${id}/approve-draft`, 'POST', data, success, error);

export const ResolveEmailService = (id, data, success, error) =>
    _fetchService(`gmail/${id}/resolve`, 'POST', data, success, error);

export const SendEmailService = (data, success, error) =>
    _fetchService('gmail/send', 'POST', data, success, error);

export const GetGmailAnalyticsService = (success, error) =>
    _fetchService('gmail/analytics', 'GET', null, success, error);

// ── Calendar ──────────────────────────────────────────────────────────────────

export const ScheduleMeetingService = (data, success, error) =>
    _fetchService('calendar/schedule', 'POST', data, success, error);

export const GetCalendarEventsService = (params = {}, success, error) => {
    const qs = new URLSearchParams();
    if (params.status)  qs.set('status', params.status);
    if (params.lead_id) qs.set('lead_id', params.lead_id);
    const query = qs.toString();
    return _fetchService(`calendar/${query ? '?' + query : ''}`, 'GET', null, success, error);
};

// ── LinkedIn ──────────────────────────────────────────────────────────────────

export const GetLinkedInStatsService = (success, error) =>
    _fetchService('linkedin/stats', 'GET', null, success, error);

export const GetLinkedInOutreachService = (params = {}, success, error) => {
    const qs = new URLSearchParams();
    if (params.page)               qs.set('page', params.page);
    if (params.limit)              qs.set('limit', params.limit);
    if (params.connection_status)  qs.set('connection_status', params.connection_status);
    if (params.message_status)     qs.set('message_status', params.message_status);
    if (params.role_category)      qs.set('role_category', params.role_category);
    const query = qs.toString();
    return _fetchService(`linkedin/${query ? '?' + query : ''}`, 'GET', null, success, error);
};

export const QueueConnectionService = (id, success, error) =>
    _fetchService(`linkedin/${id}/queue-connection`, 'POST', null, success, error);

export const QueueMessageService = (id, success, error) =>
    _fetchService(`linkedin/${id}/queue-message`, 'POST', null, success, error);

// ── RAG / AI ──────────────────────────────────────────────────────────────────

export const QueryRAGService = (data, success, error) =>
    _fetchService('ai/query', 'POST', data, success, error);

export const GetRAGAnalyticsService = (success, error) =>
    _fetchService('ai/analytics', 'GET', null, success, error);

// ── Products: Knowledge base ───────────────────────────────────────────────────

export const AddProductKnowledgeService = (productId, data, success, error) =>
    _fetchService(`products/${productId}/knowledge`, 'POST', data, success, error);

export const GetProductKnowledgeService = (productId, success, error) =>
    _fetchService(`products/${productId}/knowledge`, 'GET', null, success, error);

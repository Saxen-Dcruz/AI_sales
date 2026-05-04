import ApplicationStore from "../utils/ApplicationStore";

const successCaseCode = [200, 201];

const _fetchService = (PATH, serviceMethod, data, successCallback, errorCallBack) => {
    const { accessToken, userDetails } = ApplicationStore().getStorage("userDetails") || {};
    const END_POINT = import.meta.env.VITE_API_URL;

    if (!userDetails) {
        if (typeof errorCallBack === "function") {
            errorCallBack(401, "Session expired — please log in again.");
        }
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
            if (error.errorObject && typeof error.errorObject.then === "function") {
                error.errorObject.then((errorResponse) => {
                    if (error.errorStatus === 400 && errorResponse.message === "Token is required") {
                        ApplicationStore().clearStorage();
                    }
                    errorCallBack(error.errorStatus, errorResponse.message);
                });
            } else {
                errorCallBack(0, error.message || "Network error");
            }
        });
};

// ─── Auth ───────────────────────────────────────────────────────────────────

export const LoginService = (data) => {
    const PATH = "auth/login";
    const END_POINT = import.meta.env.VITE_API_URL;
    const headers = {
        Accept: "application/json",
        "Content-Type": "application/json",
    };
    return fetch(END_POINT + PATH, {
        method: "POST",
        mode: "cors",
        cache: "no-cache",
        credentials: "same-origin",
        headers,
        redirect: "follow",
        referrerPolicy: "no-referrer",
        body: JSON.stringify(data),
    });
};

export const LogoutService = (data, sucess, error) =>
    _fetchService("auth/logout", "POST", data, sucess, error);

export const GetCurrentUserService = (sucess, error) =>
    _fetchService("auth/me", "GET", null, sucess, error);

// ─── Products ────────────────────────────────────────────────────────────────

export const AddProductService = (data, sucess, error) =>
    _fetchService("products/", "POST", data, sucess, error);

export const ShowAllProductService = (data, sucess, error) =>
    _fetchService("products/", "GET", data, sucess, error);

export const ShowOneProductService = (data, sucess, error) =>
    _fetchService(`products/${data.id}`, "GET", null, sucess, error);

export const EditProductService = (id, data, sucess, error) =>
    _fetchService(`products/${id}`, "PATCH", data, sucess, error);

export const DeleteProductService = (id, sucess, error) =>
    _fetchService(`products/${id}`, "DELETE", null, sucess, error);

export const ToggleActiveInactiveService = (id, sucess, error) =>
    _fetchService(`products/${id}/availability`, "PATCH", null, sucess, error);

// Product Knowledge Base
export const GetAllEmbeddingsService = (sucess, error) =>
    _fetchService("products/embeddings", "GET", null, sucess, error);

export const GetProductEmbeddingsService = (productId, sucess, error) =>
    _fetchService(`products/${productId}/embeddings`, "GET", null, sucess, error);

export const GetProductKnowledgeService = (productId, sucess, error) =>
    _fetchService(`products/${productId}/knowledge`, "GET", null, sucess, error);

export const AddProductKnowledgeService = (productId, data, sucess, error) =>
    _fetchService(`products/${productId}/knowledge`, "POST", data, sucess, error);

export const UpdateProductKnowledgeService = (productId, entryId, data, sucess, error) =>
    _fetchService(`products/${productId}/knowledge/${entryId}`, "PATCH", data, sucess, error);

export const DeleteProductKnowledgeService = (productId, entryId, sucess, error) =>
    _fetchService(`products/${productId}/knowledge/${entryId}`, "DELETE", null, sucess, error);

// ─── Leads ───────────────────────────────────────────────────────────────────

export const GetAllLeadsService = (params, sucess, error) => {
    const query = new URLSearchParams(params || {}).toString();
    return _fetchService(`leads/?${query}`, "GET", null, sucess, error);
};

export const GetOneLeadService = (id, sucess, error) =>
    _fetchService(`leads/${id}`, "GET", null, sucess, error);

export const CreateLeadService = (data, sucess, error) =>
    _fetchService("leads/", "POST", data, sucess, error);

export const UpdateLeadService = (id, data, sucess, error) =>
    _fetchService(`leads/${id}`, "PATCH", data, sucess, error);

export const DeleteLeadService = (id, sucess, error) =>
    _fetchService(`leads/${id}`, "DELETE", null, sucess, error);

export const GetLeadClassificationSummaryService = (sucess, error) =>
    _fetchService("leads/classification-summary", "GET", null, sucess, error);

export const ReclassifyLeadService = (id, sucess, error) =>
    _fetchService(`leads/${id}/reclassify`, "POST", null, sucess, error);

export const GetLeadScoreBreakdownService = (id, sucess, error) =>
    _fetchService(`leads/${id}/score-breakdown`, "GET", null, sucess, error);

export const GetLeadSentimentTimelineService = (id, sucess, error) =>
    _fetchService(`leads/${id}/sentiment-timeline`, "GET", null, sucess, error);

// ─── Companies ───────────────────────────────────────────────────────────────

export const GetAllCompaniesService = (params, sucess, error) => {
    const query = new URLSearchParams(params || {}).toString();
    return _fetchService(`companies/?${query}`, "GET", null, sucess, error);
};

export const GetOneCompanyService = (id, sucess, error) =>
    _fetchService(`companies/${id}`, "GET", null, sucess, error);

export const CreateCompanyService = (data, sucess, error) =>
    _fetchService("companies/", "POST", data, sucess, error);

export const UpdateCompanyService = (id, data, sucess, error) =>
    _fetchService(`companies/${id}`, "PATCH", data, sucess, error);

export const DeleteCompanyService = (id, sucess, error) =>
    _fetchService(`companies/${id}`, "DELETE", null, sucess, error);

// ─── Deals ───────────────────────────────────────────────────────────────────

export const GetAllDealsService = (params, sucess, error) => {
    const query = new URLSearchParams(params || {}).toString();
    return _fetchService(`deals/?${query}`, "GET", null, sucess, error);
};

export const GetOneDealService = (id, sucess, error) =>
    _fetchService(`deals/${id}`, "GET", null, sucess, error);

export const CreateDealService = (data, sucess, error) =>
    _fetchService("deals/", "POST", data, sucess, error);

export const UpdateDealService = (id, data, sucess, error) =>
    _fetchService(`deals/${id}`, "PATCH", data, sucess, error);

export const DeleteDealService = (id, sucess, error) =>
    _fetchService(`deals/${id}`, "DELETE", null, sucess, error);

// ─── Calls ───────────────────────────────────────────────────────────────────

export const GetAllCallsService = (params, sucess, error) => {
    const query = new URLSearchParams(params || {}).toString();
    return _fetchService(`calls/?${query}`, "GET", null, sucess, error);
};

export const GetOneCallService = (id, sucess, error) =>
    _fetchService(`calls/${id}`, "GET", null, sucess, error);

export const CreateCallService = (data, sucess, error) =>
    _fetchService("calls/", "POST", data, sucess, error);

export const UpdateCallService = (id, data, sucess, error) =>
    _fetchService(`calls/${id}`, "PATCH", data, sucess, error);

export const SubmitTranscriptService = (id, data, sucess, error) =>
    _fetchService(`calls/${id}/transcript`, "POST", data, sucess, error);

export const GetCallAnalyticsService = (sucess, error) =>
    _fetchService("calls/analytics", "GET", null, sucess, error);

export const GetCallGapsService = (sucess, error) =>
    _fetchService("calls/gaps", "GET", null, sucess, error);

export const ResolveCallGapService = (callId, gapIndex, answer, sucess, error) =>
    _fetchService(`calls/${callId}/gaps/resolve`, "POST", { gap_index: gapIndex, answer }, sucess, error);

// ─── AI & RAG Analytics ──────────────────────────────────────────────────────

export const GetAIAnalyticsService = (sucess, error) =>
    _fetchService("ai/analytics", "GET", null, sucess, error);

export const GetAILogsService = (params, sucess, error) => {
    const queryParams = new URLSearchParams(params).toString();
    return _fetchService(`ai/analytics/logs?${queryParams}`, "GET", null, sucess, error);
};

export const GetGapAnalyticsService = (sucess, error) =>
    _fetchService("ai/analytics/gaps", "GET", null, sucess, error);

export const GetProductSentimentService = (sucess, error) =>
    _fetchService("ai/analytics/product-sentiment", "GET", null, sucess, error);

// ─── Gmail ───────────────────────────────────────────────────────────────────

export const GetEmailByIdService = (id, sucess, error) =>
    _fetchService(`gmail/${id}`, "GET", null, sucess, error);

export const GetGmailMessagesService = (params, sucess, error) => {
    const query = new URLSearchParams(params || {}).toString();
    return _fetchService(`gmail/?${query}`, "GET", null, sucess, error);
};

export const SyncGmailService = (sucess, error) =>
    _fetchService("gmail/sync", "POST", null, sucess, error);

export const GetEmailGapsService = (sucess, error) =>
    _fetchService("gmail/gaps", "GET", null, sucess, error);

export const ResolveEmailGapService = (emailId, gapIndex, answer, sucess, error) =>
    _fetchService(`gmail/${emailId}/gaps/resolve`, "POST", { gap_index: gapIndex, answer }, sucess, error);

export const ApproveDraftService = (emailId, data, sucess, error) =>
    _fetchService(`gmail/${emailId}/approve-draft`, "POST", data, sucess, error);

export const DiscardDraftService = (emailId, sucess, error) =>
    _fetchService(`gmail/${emailId}/discard-draft`, "POST", null, sucess, error);

export const ResolveEmailService = (emailId, data, sucess, error) =>
    _fetchService(`gmail/${emailId}/resolve`, "POST", data, sucess, error);

export const GenerateDraftService = (data, sucess, error) =>
    _fetchService("gmail/generate-draft", "POST", data, sucess, error);

export const SendEmailService = (data, sucess, error) =>
    _fetchService("gmail/send", "POST", data, sucess, error);

export const GetGmailAnalyticsService = (sucess, error) =>
    _fetchService("gmail/analytics", "GET", null, sucess, error);

export const GetEmailSequencesService = (params, sucess, error) => {
    const query = new URLSearchParams(params || {}).toString();
    return _fetchService(`gmail/sequences?${query}`, "GET", null, sucess, error);
};

export const CreateEmailSequenceService = (data, sucess, error) =>
    _fetchService("gmail/sequences", "POST", data, sucess, error);

export const PauseEmailSequenceService = (id, sucess, error) =>
    _fetchService(`gmail/sequences/${id}/pause`, "POST", null, sucess, error);

export const CancelEmailSequenceService = (id, sucess, error) =>
    _fetchService(`gmail/sequences/${id}/cancel`, "POST", null, sucess, error);

// ─── Calendar ────────────────────────────────────────────────────────────────

export const GetAvailabilityService = (sucess, error) =>
    _fetchService("calendar/availability", "GET", null, sucess, error);

export const UpdateAvailabilityDayService = (dayOfWeek, data, sucess, error) =>
    _fetchService(`calendar/availability/${dayOfWeek}`, "PUT", data, sucess, error);

export const GetSchedulingConfigService = (sucess, error) =>
    _fetchService("calendar/scheduling-config", "GET", null, sucess, error);

export const UpdateSchedulingConfigService = (data, sucess, error) =>
    _fetchService("calendar/scheduling-config", "PATCH", data, sucess, error);

export const GetCalendarEventsService = (params, sucess, error) => {
    const query = new URLSearchParams(params || {}).toString();
    return _fetchService(`calendar/?${query}`, "GET", null, sucess, error);
};

export const ScheduleMeetingService = (data, sucess, error) =>
    _fetchService("calendar/schedule", "POST", data, sucess, error);

export const CancelEventService = (id, sucess, error) =>
    _fetchService(`calendar/${id}`, "DELETE", null, sucess, error);

export const GetBlockedTimesService = (sucess, error) =>
    _fetchService("calendar/blocked-times", "GET", null, sucess, error);

export const AddBlockedTimeService = (data, sucess, error) =>
    _fetchService("calendar/blocked-times", "POST", data, sucess, error);

export const DeleteBlockedTimeService = (id, sucess, error) =>
    _fetchService(`calendar/blocked-times/${id}`, "DELETE", null, sucess, error);

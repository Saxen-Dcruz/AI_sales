import ApplicationStore from "../utils/ApplicationStore";

const successCaseCode = [200, 201];
const END_POINT = import.meta.env.VITE_API_URL;

// ── Silent token refresh ──────────────────────────────────────────────────────
let _isRefreshing = false;
let _refreshQueue = []; // [{resolve, reject}] — requests waiting for new token

function _processQueue(error, newToken = null) {
    _refreshQueue.forEach(({ resolve, reject }) =>
        error ? reject(error) : resolve(newToken)
    );
    _refreshQueue = [];
}

async function _doRefresh() {
    const stored = ApplicationStore().getStorage("userDetails") || {};
    const refreshToken = stored.refreshToken;
    if (!refreshToken) throw new Error("No refresh token stored");

    const res = await fetch(END_POINT + "auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
        mode: "cors",
        credentials: "same-origin",
    });

    if (!res.ok) {
        ApplicationStore().clearStorage();
        throw new Error("Refresh failed");
    }

    const data = await res.json();
    ApplicationStore().setStorage("userDetails", {
        ...stored,
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
    });
    return data.access_token;
}

function _getAuthHeaders(accessToken) {
    const { userDetails } = ApplicationStore().getStorage("userDetails") || {};
    if (!userDetails) return {};
    const { id, email, userRole, companyCode, semesterId, branch, instituteid } = userDetails;
    return {
        authorization: `Bearer ${accessToken}`,
        companyCode: `${companyCode}`,
        userId: `${id}`,
        userEmail: `${email}`,
        userRole: `${userRole}`,
        semesterId: `${semesterId}`,
        branch: `${branch}`,
        instituteid: `${instituteid}`,
    };
}

function _buildRequestOptions(serviceMethod, data, accessToken) {
    const isFormData = data instanceof FormData;
    const authHeaders = _getAuthHeaders(accessToken);
    const headers = isFormData
        ? authHeaders
        : { "Content-Type": "application/json", ...authHeaders };
    return {
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
}

const _fetchService = (PATH, serviceMethod, data, successCallback, errorCallBack) => {
    const stored = ApplicationStore().getStorage("userDetails") || {};
    const { accessToken, userDetails } = stored;

    if (!userDetails) {
        if (typeof errorCallBack === "function") {
            errorCallBack(401, "Session expired — please log in again.");
        }
        return Promise.reject("Unauthorized: No user details found.");
    }

    const _execute = (token) =>
        fetch(END_POINT + PATH, _buildRequestOptions(serviceMethod, data, token));

    return _execute(accessToken)
        .then(async (response) => {
            // ── 401: attempt silent token refresh then retry once ─────────────
            if (response.status === 401) {
                if (_isRefreshing) {
                    // Queue this request until the in-flight refresh finishes
                    return new Promise((resolve, reject) => {
                        _refreshQueue.push({ resolve, reject });
                    }).then((newToken) =>
                        _execute(newToken).then(async (retryRes) => {
                            if (successCaseCode.includes(retryRes.status)) return retryRes.json();
                            const err = await retryRes.json().catch(() => ({}));
                            throw { errorStatus: retryRes.status, errorMessage: err.detail || err.message };
                        })
                    );
                }

                _isRefreshing = true;
                try {
                    const newToken = await _doRefresh();
                    _processQueue(null, newToken);
                    const retryRes = await _execute(newToken);
                    if (successCaseCode.includes(retryRes.status)) return retryRes.json();
                    const err = await retryRes.json().catch(() => ({}));
                    throw { errorStatus: retryRes.status, errorMessage: err.detail || err.message };
                } catch (refreshErr) {
                    _processQueue(refreshErr, null);
                    throw { errorStatus: 401, errorMessage: "Session expired — please log in again." };
                } finally {
                    _isRefreshing = false;
                }
            }

            if (successCaseCode.includes(response.status)) return response.json();
            const errBody = await response.json().catch(() => ({}));
            throw { errorStatus: response.status, errorMessage: errBody.detail || errBody.message };
        })
        .then((dataResponse) => successCallback(dataResponse))
        .catch((error) => {
            if (error.errorStatus === 400 && error.errorMessage === "Token is required") {
                ApplicationStore().clearStorage();
            }
            if (typeof errorCallBack === "function") {
                errorCallBack(error.errorStatus ?? 0, error.errorMessage || error.message || "Network error");
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

// ─── User Management (super-admin) ───────────────────────────────────────────
export const ListUsersService = (sucess, error) =>
    _fetchService("users", "GET", null, sucess, error);
export const CreateUserService = (data, sucess, error) =>
    _fetchService("users", "POST", data, sucess, error);
export const UpdateUserService = (id, data, sucess, error) =>
    _fetchService(`users/${id}`, "PATCH", data, sucess, error);
export const DeleteUserService = (id, sucess, error) =>
    _fetchService(`users/${id}`, "DELETE", null, sucess, error);
export const ChangePasswordSelfService = (data, sucess, error) =>
    _fetchService("users/me/password", "PATCH", data, sucess, error);

// ─── Products ────────────────────────────────────────────────────────────────

export const AddProductService = (data, sucess, error) =>
    _fetchService("products/", "POST", data, sucess, error);

export const ShowAllProductService = (data, sucess, error) =>
    _fetchService("products/?limit=1000", "GET", data, sucess, error);

export const ShowOneProductService = (data, sucess, error) =>
    _fetchService(`products/${data.id}`, "GET", null, sucess, error);

export const EditProductService = (id, data, sucess, error) =>
    _fetchService(`products/${id}`, "PATCH", data, sucess, error);

export const DeleteProductService = (id, sucess, error) =>
    _fetchService(`products/${id}`, "DELETE", null, sucess, error);

export const ToggleActiveInactiveService = (id, sucess, error) =>
    _fetchService(`products/${id}/availability`, "PATCH", null, sucess, error);

export const GetProductCategoriesService = (sucess, error) =>
    _fetchService("products/categories", "GET", null, sucess, error);

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

export const UpdateProductChunkService = (productId, chunkId, data, sucess, error) =>
    _fetchService(`products/${productId}/chunks/${chunkId}`, "PATCH", data, sucess, error);

export const DeleteProductChunkService = (productId, chunkId, sucess, error) =>
    _fetchService(`products/${productId}/chunks/${chunkId}`, "DELETE", null, sucess, error);

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

export const GetDealAnalyticsService = (sucess, error) =>
    _fetchService("deals/analytics", "GET", null, sucess, error);

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

export const ResolveCallGapService = (callId, gapIndex, answer, category, productId, sucess, error) =>
    _fetchService(`calls/${callId}/gaps/resolve`, "POST", {
        gap_index: gapIndex, answer,
        ...(category ? { category } : {}),
        ...(productId ? { product_id: productId } : {}),
    }, sucess, error);

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

// Fetch all messages of a Gmail thread (chronological)
export const GetGmailThreadService = (threadId, sucess, error) =>
    _fetchService(`gmail/threads/${threadId}`, "GET", null, sucess, error);

// CRM record panel for an email's linked lead/contact + deal
export const GetEmailCrmContextService = (emailId, sucess, error) =>
    _fetchService(`gmail/${emailId}/crm`, "GET", null, sucess, error);

// All messages from/to a specific contact email address (full conversation history)
export const GetContactMessagesService = (senderEmail, params, sucess, error) => {
    const q = new URLSearchParams({ sender_email: senderEmail, business_only: false, limit: 200, page: 1, ...params }).toString()
    return _fetchService(`gmail/?${q}`, "GET", null, sucess, error)
}

export const SyncGmailService = (sucess, error) =>
    _fetchService("gmail/sync", "POST", null, sucess, error);

export const GetEmailGapsService = (sucess, error) =>
    _fetchService("gmail/gaps", "GET", null, sucess, error);

export const ResolveEmailGapService = (emailId, gapIndex, answer, category, productId, sucess, error) =>
    _fetchService(`gmail/${emailId}/gaps/resolve`, "POST", {
        gap_index: gapIndex, answer,
        ...(category ? { category } : {}),
        ...(productId ? { product_id: productId } : {}),
    }, sucess, error);

export const ApproveDraftService = (emailId, data, sucess, error) =>
    _fetchService(`gmail/${emailId}/approve-draft`, "POST", data, sucess, error);

export const DiscardDraftService = (emailId, sucess, error) =>
    _fetchService(`gmail/${emailId}/discard-draft`, "POST", null, sucess, error);

export const ResolveEmailService = (emailId, data, sucess, error) =>
    _fetchService(`gmail/${emailId}/resolve`, "POST", data, sucess, error);

export const MarkEmailReadService = (emailId, sucess, error) =>
    _fetchService(`gmail/${emailId}/read`, "POST", {}, sucess, error);

export const GenerateDraftService = (data, sucess, error) =>
    _fetchService("gmail/generate-draft", "POST", data, sucess, error);

export const SendEmailService = (data, sucess, error) =>
    _fetchService("gmail/send", "POST", data, sucess, error);

export const GetGmailAnalyticsService = (since = "7d", accountId = null, sucess, error) => {
    const q = new URLSearchParams({ since })
    if (accountId) q.set("account_id", accountId)
    return _fetchService(`gmail/analytics?${q}`, "GET", null, sucess, error)
}

// ── Settings — Email Accounts ─────────────────────────────────────────────────
export const GetEmailAccountsService = (sucess, error) =>
    _fetchService("settings/email-accounts", "GET", null, sucess, error)

export const GetEmailAccountAuthUrlService = (sucess, error) =>
    _fetchService("settings/email-accounts/auth-url", "GET", null, sucess, error)

export const UpdateEmailAccountService = (id, data, sucess, error) =>
    _fetchService(`settings/email-accounts/${id}`, "PATCH", data, sucess, error)

export const SetPrimaryEmailAccountService = (id, sucess, error) =>
    _fetchService(`settings/email-accounts/${id}/set-primary`, "POST", null, sucess, error)

export const DeleteEmailAccountService = (id, sucess, error) =>
    _fetchService(`settings/email-accounts/${id}`, "DELETE", null, sucess, error)

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

export const RescheduleEventService = (id, data, sucess, error) =>
    _fetchService(`calendar/${id}/reschedule`, "PATCH", data, sucess, error);

export const GetBlockedTimesService = (sucess, error) =>
    _fetchService("calendar/blocked-times", "GET", null, sucess, error);

export const AddBlockedTimeService = (data, sucess, error) =>
    _fetchService("calendar/blocked-times", "POST", data, sucess, error);

export const DeleteBlockedTimeService = (id, sucess, error) =>
    _fetchService(`calendar/blocked-times/${id}`, "DELETE", null, sucess, error);

// ─── Email Templates ─────────────────────────────────────────────────────────

export const GetEmailTemplatesService = (sucess, error) =>
    _fetchService("email-templates/", "GET", null, sucess, error);

export const CreateEmailTemplateService = (data, sucess, error) =>
    _fetchService("email-templates/", "POST", data, sucess, error);

export const UpdateEmailTemplateService = (id, data, sucess, error) =>
    _fetchService(`email-templates/${id}`, "PATCH", data, sucess, error);

export const DeleteEmailTemplateService = (id, sucess, error) =>
    _fetchService(`email-templates/${id}`, "DELETE", null, sucess, error);

// ─── Lead Generation ─────────────────────────────────────────────────────────

// Discovery
export const RunDiscoverySearchService = (data, success, error) =>
    _fetchService("lead-gen/discovery/search", "POST", data, success, error);
export const RunLinkedInScrapeService = (params, success, error) => {
    const q = new URLSearchParams(params).toString()
    return _fetchService(`lead-gen/discovery/linkedin-scrape?${q}`, "POST", null, success, error)
}
export const GetProspectCompaniesService = (params, success, error) => {
    const q = new URLSearchParams(params).toString()
    return _fetchService(`lead-gen/discovery/companies?${q}`, "GET", null, success, error)
}
export const GetProspectContactsService = (params, success, error) => {
    const q = new URLSearchParams(params).toString()
    return _fetchService(`lead-gen/discovery/contacts?${q}`, "GET", null, success, error)
}
export const ScoreCompaniesService = (ids, success, error) =>
    _fetchService("lead-gen/discovery/score", "POST", ids || null, success, error);

// Campaigns
export const GetCampaignsService = (success, error) =>
    _fetchService("lead-gen/campaigns", "GET", null, success, error);
export const CreateCampaignService = (data, success, error) =>
    _fetchService("lead-gen/campaigns", "POST", data, success, error);
export const UpdateCampaignService = (id, data, success, error) =>
    _fetchService(`lead-gen/campaigns/${id}`, "PATCH", data, success, error);
export const DeleteCampaignService = (id, success, error) =>
    _fetchService(`lead-gen/campaigns/${id}`, "DELETE", null, success, error);
export const AddContactsToCampaignService = (id, contactIds, success, error) =>
    _fetchService(`lead-gen/campaigns/${id}/add-contacts`, "POST", { contact_ids: contactIds }, success, error);
export const GenerateDraftsService = (id, success, error) =>
    _fetchService(`lead-gen/campaigns/${id}/generate-drafts`, "POST", null, success, error);

// Outreach
export const GetOutreachQueueService = (params, success, error) => {
    const q = new URLSearchParams(params).toString()
    return _fetchService(`lead-gen/outreach/queue?${q}`, "GET", null, success, error)
}
export const ApproveOutreachService = (id, data, success, error) =>
    _fetchService(`lead-gen/outreach/${id}/approve`, "POST", data, success, error);
export const SendOutreachService = (id, success, error) =>
    _fetchService(`lead-gen/outreach/${id}/send`, "POST", null, success, error);
export const RejectOutreachService = (id, success, error) =>
    _fetchService(`lead-gen/outreach/${id}/reject`, "POST", null, success, error);
export const SetInterestService = (id, status, success, error) =>
    _fetchService(`lead-gen/outreach/${id}/interest`, "PATCH", { status }, success, error);
export const GetOutreachThreadService = (id, success, error) =>
    _fetchService(`lead-gen/outreach/${id}/thread`, "GET", null, success, error);
export const SendManualReplyService = (id, body, success, error) =>
    _fetchService(`lead-gen/outreach/${id}/reply`, "POST", { edit_body: body }, success, error);
export const GenerateAIReplyService = (id, success, error) =>
    _fetchService(`lead-gen/outreach/${id}/generate-reply`, "POST", null, success, error);

// Analytics
export const GetLeadGenAnalyticsService = (success, error) =>
    _fetchService("lead-gen/analytics/dashboard", "GET", null, success, error);

// LinkedIn
export const GetLinkedInStatsService = (success, error) =>
    _fetchService("linkedin/stats", "GET", null, success, error);
export const GetLinkedInBudgetService = (success, error) =>
    _fetchService("linkedin/budget", "GET", null, success, error);
export const GetLinkedInOutreachService = (params, success, error) => {
    const q = new URLSearchParams(params).toString()
    return _fetchService(`linkedin?${q}`, "GET", null, success, error)
}
export const TriggerLinkedInDiscoveryService = (data, success, error) =>
    _fetchService("linkedin/discover-companies", "POST", data, success, error);
export const QueueConnectionService = (id, success, error) =>
    _fetchService(`linkedin/${id}/queue-connection`, "POST", null, success, error);
export const QueueMessageService = (id, success, error) =>
    _fetchService(`linkedin/${id}/queue-message`, "POST", null, success, error);
export const MarkConnectedService = (id, success, error) =>
    _fetchService(`linkedin/${id}/connected`, "PATCH", null, success, error);
export const MarkMessageSentService = (id, success, error) =>
    _fetchService(`linkedin/${id}/message-sent`, "PATCH", null, success, error);
export const MarkReplyReceivedService = (id, reply, success, error) =>
    _fetchService(`linkedin/${id}/reply`, "PATCH", { reply_preview: reply }, success, error);

// LinkedIn OAuth accounts
export const GetLinkedInAccountsService = (success, error) =>
    _fetchService("linkedin-accounts", "GET", null, success, error);
export const GetLinkedInAuthUrlService = (success, error) =>
    _fetchService("linkedin-accounts/auth-url", "GET", null, success, error);
export const DisconnectLinkedInAccountService = (id, success, error) =>
    _fetchService(`linkedin-accounts/${id}`, "DELETE", null, success, error);

// LinkedIn scraper session (li_at cookie)
export const GetScraperSessionStatusService = (success, error) =>
    _fetchService("linkedin-accounts/scraper-session", "GET", null, success, error);
export const SaveScraperSessionService = (li_at, success, error) =>
    _fetchService("linkedin-accounts/scraper-session", "POST", { li_at }, success, error);
export const ClearScraperSessionService = (success, error) =>
    _fetchService("linkedin-accounts/scraper-session", "DELETE", null, success, error);

// ─── WhatsApp ─────────────────────────────────────────────────────────────────

// Account management (Settings)
export const GetWhatsAppAccountsService = (success, error) =>
    _fetchService("settings/whatsapp-accounts", "GET", null, success, error);

export const AddWhatsAppAccountService = (data, success, error) =>
    _fetchService("settings/whatsapp-accounts", "POST", data, success, error);

export const UpdateWhatsAppAccountService = (id, data, success, error) =>
    _fetchService(`settings/whatsapp-accounts/${id}`, "PATCH", data, success, error);

export const DeleteWhatsAppAccountService = (id, success, error) =>
    _fetchService(`settings/whatsapp-accounts/${id}`, "DELETE", null, success, error);

export const SetPrimaryWhatsAppAccountService = (id, success, error) =>
    _fetchService(`settings/whatsapp-accounts/${id}/set-primary`, "POST", null, success, error);

// Inbox
export const GetWhatsAppMessagesService = (params, success, error) => {
    const q = new URLSearchParams(params || {}).toString();
    return _fetchService(`whatsapp/?${q}`, "GET", null, success, error);
};

export const GetWhatsAppMessageService = (id, success, error) =>
    _fetchService(`whatsapp/${id}`, "GET", null, success, error);

export const ApproveWhatsAppDraftService = (id, data, success, error) =>
    _fetchService(`whatsapp/${id}/approve-draft`, "POST", data, success, error);

export const DiscardWhatsAppDraftService = (id, success, error) =>
    _fetchService(`whatsapp/${id}/discard-draft`, "POST", null, success, error);

export const ResolveWhatsAppMessageService = (id, success, error) =>
    _fetchService(`whatsapp/${id}/resolve`, "POST", null, success, error);

export const ResolveWhatsAppGapService = (id, data, success, error) =>
    _fetchService(`whatsapp/${id}/gaps/resolve`, "POST", data, success, error);

export const GetWhatsAppGapsService = (success, error) =>
    _fetchService("whatsapp/gaps", "GET", null, success, error);

export const SendWhatsAppMessageService = (data, success, error) =>
    _fetchService("whatsapp/send", "POST", data, success, error);

export const GetWhatsAppAnalyticsService = (success, error) =>
    _fetchService("whatsapp/analytics", "GET", null, success, error);

// Conversation history per sender
export const GetWhatsAppConversationService = (phoneNumber, params, success, error) => {
    const q = new URLSearchParams(params || {}).toString()
    return _fetchService(`whatsapp/conversations/${encodeURIComponent(phoneNumber)}?${q}`, "GET", null, success, error)
}

export const GetGmailConversationService = (senderEmail, params, success, error) => {
    const q = new URLSearchParams(params || {}).toString()
    return _fetchService(`gmail/conversations/${encodeURIComponent(senderEmail)}?${q}`, "GET", null, success, error)
}

// ─── Dashboard Intelligence ───────────────────────────────────────────────────

export const GetDashboardSummaryService = (success, error) =>
    _fetchService("dashboard/summary", "GET", null, success, error)

export const GetCallIntelligenceService = (days = 30, success, error) =>
    _fetchService(`dashboard/call-intelligence?days=${days}`, "GET", null, success, error)

// ─── Voice Bridge ─────────────────────────────────────────────────────────────

export const GetVoiceAnalyticsService = (success, error) =>
    _fetchService("voice/analytics", "GET", null, success, error)

export const CreateVoiceRoomService = (payload, success, error) =>
    _fetchService("voice/rooms", "POST", payload, success, error)

export const GetVoiceSessionService = (roomName, success, error) =>
    _fetchService(`voice/rooms/${roomName}`, "GET", null, success, error)

export const GetCompanySettingsService = (success, error) =>
    _fetchService("settings/company", "GET", null, success, error)

export const UpdateCompanySettingsService = (data, success, error) =>
    _fetchService("settings/company", "PATCH", data, success, error)

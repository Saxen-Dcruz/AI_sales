import ApplicationStore from "../utils/ApplicationStore";

const successCaseCode = [200, 201];

const _fetchService = (PATH, serviceMethod, data, successCallback, errorCallBack) => {
    const { accessToken, userDetails } = ApplicationStore().getStorage("userDetails") || {};
    const END_POINT = import.meta.env.VITE_API_URL || 'http://192.168.1.104:8003/api/v1/';

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
        ? authHeaders // omit Content-Type so browser sets multipart/form-data boundary
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
            error.errorObject.then((errorResponse) => {
                if (error.errorStatus === 400 && errorResponse.message === "Token is required") {
                    ApplicationStore().clearStorage();
                }
                errorCallBack(error.errorStatus, errorResponse.message);
            });
        });
};



export const
    LoginService = (data) => {
        const PATH = 'auth/login';
        // const END_POINT = 'http://192.168.1.104:8003/api/v1/';
        const END_POINT = 'http://192.168.1.104:8003/api/v1/';
        const SERVICE_METHOD = 'POST';
        const headers = {
            Accept: 'application/json',
            'Content-Type': 'application/json',
        };

        return fetch(END_POINT + PATH, {
            method: SERVICE_METHOD,
            mode: 'cors',
            cache: 'no-cache',
            credentials: 'same-origin',
            headers,
            redirect: 'follow',
            referrerPolicy: 'no-referrer',
            body: JSON.stringify(data),
        });
    };



export const LogoutService = (data, sucess, error) => {
    return _fetchService('auth/logout', 'POST', data, sucess, error);
}

export const GetCurrentUserService = (sucess, error) => {
    return _fetchService('auth/me', 'GET', null, sucess, error);
}

export const AddProductService = (data, sucess, error) => {
    return _fetchService('products/', 'POST', data, sucess, error);
}

export const ShowAllProductService = (data, sucess, error) => {
    return _fetchService('products/', 'GET', data, sucess, error);
}

export const ShowOneProductService = (data, sucess, error) => {
    return _fetchService(`products/${data.id}`, 'GET', null, sucess, error);
}

export const EditProductService = (id, data, sucess, error) => {
    return _fetchService(`products/${id}`, 'PUT', data, sucess, error);
}

export const DeleteProductService = (id, sucess, error) => {
    return _fetchService(`products/${id}`, 'DELETE', null, sucess, error);
}


export const ToggleActiveInactiveService = (data, sucess, error) => {
    return _fetchService('toggle-active-inactive', 'PUT', data, sucess, error);
}

// AI & RAG Analytics
export const GetAIAnalyticsService = (sucess, error) => {
    return _fetchService('ai/analytics', 'GET', null, sucess, error);
}

export const GetAILogsService = (params, sucess, error) => {
    const queryParams = new URLSearchParams(params).toString();
    return _fetchService(`ai/analytics/logs?${queryParams}`, 'GET', null, sucess, error);
}

export const GetGapsService = (sucess, error) => {
    return _fetchService('gaps', 'GET', null, sucess, error);
}

export const ResolveGapService = (id, data, sucess, error) => {
    return _fetchService(`gaps/${id}/resolve`, 'POST', data, sucess, error);
}

// Gmail & Calendar
export const GetGmailMessagesService = (sucess, error) => {
    return _fetchService('gmail/messages', 'GET', null, sucess, error);
}

export const SyncGmailService = (sucess, error) => {
    return _fetchService('gmail/sync', 'POST', null, sucess, error);
}

export const GetCalendarEventsService = (sucess, error) => {
    return _fetchService('calendar/events', 'GET', null, sucess, error);
}



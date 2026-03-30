import ApplicationStore from "../utils/ApplicationStore";

const successCaseCode = [200, 201];

const _fetchService = (PATH, serviceMethod, data, successCallback, errorCallBack) => {
    const { accessToken, userDetails } = ApplicationStore().getStorage("userDetails");
    const END_POINT = process.env.REACT_APP_API_URL || 'http://192.168.1.73:8003/api/';
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
        const PATH = 'login';
        // const END_POINT = 'http://192.168.1.73:8003/api/';
        const END_POINT = 'http://192.168.1.73:8003/api/';
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
    return _fetchService('logout', 'POST', data, sucess, error);
}

export const AddProductService = (data, sucess, error) => {
    return _fetchService('add-product', 'POST', data, sucess, error);
}

export const ShowProductService = (data, sucess, error) => {
    return _fetchService('show-product', 'GET', data, sucess, error);
}

export const EditProductService = (data, sucess, error) => {
    return _fetchService('edit-product', 'PUT', data, sucess, error);
}

export const DeleteProductService = (data, sucess, error) => {
    return _fetchService('delete-product', 'DELETE', data, sucess, error);
}


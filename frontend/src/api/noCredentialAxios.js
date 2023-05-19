/**
 * @Author: Bi Ying
 * @Date:   2022-02-08 17:35:01
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-05-17 19:22:16
 */
import axios from 'axios'

axios.defaults.xsrfCookieName = "csrftoken"
axios.defaults.xsrfHeaderName = "X-CSRFToken"

async function noCredentialAxios(axiosConfig) {
    const service = axios.create({
        timeout: 20000,
        headers: {
            "Content-Type": "application/json",
        },
        xhrFields: {
            withCredentials: true,
        },
    })

    return service(axiosConfig)
}

export default noCredentialAxios

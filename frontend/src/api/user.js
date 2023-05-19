/**
 * @Author: Bi Ying
 * @Date:   2022-05-25 01:29:38
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-05-15 23:01:59
 */
export async function userInfoAPI(action, parameter) {
    return await window.pywebview.api[`user_info__${action}`](parameter)
}

export async function settingAPI(action, parameter) {
    return await window.pywebview.api[`setting__${action}`](parameter)
}

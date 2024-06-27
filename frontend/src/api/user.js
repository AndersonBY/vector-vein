/**
 * @Author: Bi Ying
 * @Date:   2022-05-25 01:29:38
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-12 02:12:45
 */
import baseAPI from './base'

export async function userInfoAPI(action, parameter) {
    return await baseAPI(`user_info__${action}`, parameter)
}

export async function settingAPI(action, parameter) {
    return await baseAPI(`setting__${action}`, parameter)
}

export async function hardwareAPI(action, parameter) {
    return await baseAPI(`hardware__${action}`, parameter)
}

export async function shortcutAPI(action, parameter) {
    return await baseAPI(`shortcut__${action}`, parameter)
}
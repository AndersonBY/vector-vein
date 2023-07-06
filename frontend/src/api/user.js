/**
 * @Author: Bi Ying
 * @Date:   2022-05-25 01:29:38
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-07-06 17:23:56
 */
import baseAPI from './base'

export async function userInfoAPI(action, parameter) {
    return await baseAPI(`user_info__${action}`, parameter)
}

export async function settingAPI(action, parameter) {
    return await baseAPI(`setting__${action}`, parameter)
}

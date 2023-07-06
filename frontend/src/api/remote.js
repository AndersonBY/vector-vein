/**
 * @Author: Bi Ying
 * @Date:   2022-05-25 01:29:38
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-07-06 17:30:55
 */
import baseAPI from './base'

export async function officialSiteAPI(action, parameter) {
    return await baseAPI(`official_site__${action}`, parameter)
}

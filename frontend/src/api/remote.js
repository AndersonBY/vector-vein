/**
 * @Author: Bi Ying
 * @Date:   2022-05-25 01:29:38
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-05-17 12:11:27
 */
export async function officialSiteAPI(action, parameter) {
    return await window.pywebview.api[`official_site__${action}`](parameter)
}

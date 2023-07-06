/**
 * @Author: Bi Ying
 * @Date:   2023-07-06 17:21:20
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-07-06 17:29:06
 */
export default async function baseAPI(path, parameter) {
    if (!window.pywebview) {
        await new Promise(resolve => setTimeout(resolve, 100))
    }
    return await window.pywebview.api[path](parameter)
}
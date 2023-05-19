/**
 * @Author: Bi Ying
 * @Date:   2022-05-25 11:47:54
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2022-05-25 12:51:17
 */
export function getPageTitle(te, t, key) {
    const hasKey = te(key)
    const title = t(`router.base`)
    if (hasKey) {
        const pageName = t(key)
        return `${pageName} - ${title}`
    }
    return `${title}`
}

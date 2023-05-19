/**
 * @Author: Bi Ying
 * @Date:   2022-05-24 14:04:48
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-05-17 11:42:37
 */
import { createI18n } from 'vue-i18n'
import zh_CN from '@/locales/zh-CN'
import en_US from '@/locales/en-US'


export const languageList = {
    'zh-CN': '中文',
    'en-US': 'English',
}

const i18n = createI18n({
    legacy: false,
    allowComposition: true,
    globalInjection: true,
    global: true,
    locale: localStorage.getItem("userSettings.language") || 'zh-CN',
    fallbackLocale: localStorage.getItem("userSettings.language") || 'zh-CN',
    messages: {
        'zh-CN': zh_CN,
        'en-US': en_US,
    }
})

export default i18n

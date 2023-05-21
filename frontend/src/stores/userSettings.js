/**
 * @Author: Bi Ying
 * @Date:   2022-12-01 17:43:11
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-05-22 01:24:14
 */
import { defineStore } from "pinia"

let userLanguage = navigator.language
if (userLanguage === 'en') {
  userLanguage = 'en-US'
}

export const useUserSettingsStore = defineStore('userSettings', {
  state: () => ({
    language: userLanguage || 'zh-CN',
    setting: {},
    tourVersion: 0,
  }),
  actions: {
    setLanguage(language) {
      this.language = language
    },
    setSetting(setting) {
      this.setting = setting
    },
    setTourVersion(tourVersion) {
      this.tourVersion = tourVersion
    },
  },
})
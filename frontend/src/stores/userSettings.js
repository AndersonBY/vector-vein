/**
 * @Author: Bi Ying
 * @Date:   2022-12-01 17:43:11
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-07-22 15:38:00
 */
import { defineStore } from "pinia"

let userLanguage = navigator.language
if (userLanguage === 'en') {
  userLanguage = 'en-US'
}

const getVueFlowStyleSettingsFromLocalStoreage = () => {
  const defaultStyleSettings = {
    edge: {
      type: 'smoothstep',
      animated: true,
      style: {
        strokeWidth: 3,
        stroke: '#565656',
      },
    },
  }
  try {
    const localStyleSettings = JSON.parse(localStorage.getItem("userSettings.vueFlowStyleSettings"))
    return localStyleSettings || defaultStyleSettings
  } catch (err) {
    return defaultStyleSettings
  }
}

export const useUserSettingsStore = defineStore('userSettings', {
  state: () => ({
    language: userLanguage || 'zh-CN',
    setting: {},
    tourVersion: 0,
    vueFlowStyleSettings: getVueFlowStyleSettingsFromLocalStoreage(),
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
    setVueFlowStyleSettings(vueFlowStyleSettings) {
      this.vueFlowStyleSettings = vueFlowStyleSettings
      localStorage.setItem("userSettings.vueFlowStyleSettings", JSON.stringify(this.vueFlowStyleSettings))
    },
  },
})
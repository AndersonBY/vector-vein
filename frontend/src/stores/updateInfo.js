import { defineStore } from 'pinia'

const DISMISSED_VERSION_STORAGE_KEY = 'updateInfo.dismissedVersion'

const getDismissedVersion = () => {
  return localStorage.getItem(DISMISSED_VERSION_STORAGE_KEY) || ''
}

export const useUpdateInfoStore = defineStore('updateInfo', {
  state: () => ({
    current: null,
    lastCheckedAt: null,
    dismissedVersion: getDismissedVersion(),
  }),
  getters: {
    hasUpdate(state) {
      return Boolean(state.current?.version)
    },
  },
  actions: {
    setCurrent(updateInfo) {
      this.current = updateInfo
      this.lastCheckedAt = Date.now()
    },
    dismiss(version) {
      this.dismissedVersion = version
      localStorage.setItem(DISMISSED_VERSION_STORAGE_KEY, version)
    },
    shouldShow(version) {
      return Boolean(version) && this.dismissedVersion !== version
    },
    clear() {
      this.current = null
      this.lastCheckedAt = null
    },
  },
})

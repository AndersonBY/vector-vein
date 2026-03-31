import { defineStore } from 'pinia'

const getDefaultState = () => ({
  items: [],
  lastUpdatedAt: null,
})

export const useGeneralQueueStore = defineStore('generalQueue', {
  state: () => getDefaultState(),
  actions: {
    setItems(items) {
      this.items = items
      this.lastUpdatedAt = Date.now()
    },
    upsertItem(item, key = 'id') {
      const itemIndex = this.items.findIndex((currentItem) => currentItem?.[key] === item?.[key])
      if (itemIndex === -1) {
        this.items.push(item)
      } else {
        this.items[itemIndex] = {
          ...this.items[itemIndex],
          ...item,
        }
      }
      this.lastUpdatedAt = Date.now()
    },
    removeItem(value, key = 'id') {
      this.items = this.items.filter((item) => item?.[key] !== value)
      this.lastUpdatedAt = Date.now()
    },
    clear() {
      Object.assign(this, getDefaultState())
    },
  },
})

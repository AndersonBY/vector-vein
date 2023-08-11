/**
 * @Author: Bi Ying
 * @Date:   2022-12-01 17:43:11
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-08-11 17:39:26
 */
import { defineStore } from "pinia"


export const useNodeMessagesStore = defineStore('nodeMessages', {
  state: () => ({
    nodeMessages: [],
    nodeMessagesCount: 0,
  }),
  actions: {
    push(message) {
      this.nodeMessages.push(message)
      this.nodeMessagesCount = this.nodeMessages.length
    },
    pop() {
      const message = this.nodeMessages.pop()
      this.nodeMessagesCount = this.nodeMessages.length
      return message
    },
  },
})
/**
 * @Author: Bi Ying
 * @Date:   2023-12-11 18:08:13
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-06 21:37:24
 */
import { defineStore } from "pinia"


export const useUserChatsStore = defineStore('userChats', {
  state: () => ({
    unsentChats: [],
    conversations: [],
    conversationsLength: 0,
  }),
  actions: {
    addUnsentChat(chat) {
      this.unsentChats.push(chat)
    },
    clearUnsentChats() {
      this.unsentChats = []
    },
    addConversation(conversation) {
      const index = this.conversations.findIndex(c => c.cid === conversation.cid)
      if (index !== -1) {
        return
      }
      this.conversations.push(conversation)
      this.conversationsLength = this.conversations.length
    },
    deleteConversation(cid) {
      this.conversations = this.conversations.filter(conversation => conversation.cid !== cid)
      this.conversationsLength = this.conversations.length
    },
    updateConversation(cid, key, value) {
      const index = this.conversations.findIndex(conversation => conversation.cid === cid)
      this.conversations[index][key] = value
    },
  },
})
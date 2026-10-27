/**
 * @Author: Bi Ying
 * @Date:   2023-12-11 18:08:13
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-06 21:37:24
 */
import { defineStore } from "pinia"
import { conversationAPI } from '@/api/chat'

const draftRequests = new WeakMap()
const requestsFor = store => {
  if (!draftRequests.has(store)) draftRequests.set(store, new Map())
  return draftRequests.get(store)
}
export const chatDraftKey = (aid, cid = '') => `${aid}:${cid || 'new'}`


export const useUserChatsStore = defineStore('userChats', {
  state: () => ({
    unsentChats: [],
    conversations: [],
    conversationsLength: 0,
    drafts: {},
  }),
  actions: {
    addUnsentChat(chat) {
      this.unsentChats = this.unsentChats.filter(item => item.cid !== chat.cid)
      this.unsentChats.push(chat)
    },
    clearUnsentChats(cid) {
      this.unsentChats = this.unsentChats.filter(item => item.cid !== cid)
    },
    getDraft(aid, cid = '') {
      const key = chatDraftKey(aid, cid)
      this.drafts[key] ||= { text: '', attachments: [], revision: 0, loaded: false }
      return this.drafts[key]
    },
    async loadDraft(aid, cid = '') {
      const draft = this.getDraft(aid, cid)
      if (draft.loaded) return draft
      const revision = draft.revision
      const res = await conversationAPI('draft', { aid, cid })
      if (res.status !== 200) throw new Error('load draft failed')
      if (draft.revision === revision) {
        draft.text = res.data.text
        draft.attachments = [...res.data.attachments]
      }
      draft.loaded = true
      return draft
    },
    saveDraft(aid, cid, text, attachments) {
      const draft = this.getDraft(aid, cid)
      Object.assign(draft, { text, attachments: [...attachments], revision: draft.revision + 1, loaded: true })
      const key = chatDraftKey(aid, cid)
      const requests = requestsFor(this)
      // Serialize writes per owner so a slow older save cannot restore submitted content.
      const pending = (requests.get(key) || Promise.resolve()).catch(() => {}).then(async () => {
        const res = await conversationAPI('draft', { aid, cid, text, attachments: [...attachments] })
        if (res.status !== 200) throw new Error('save draft failed')
      })
      requests.set(key, pending)
      return pending.finally(() => { if (requests.get(key) === pending) requests.delete(key) })
    },
    clearSubmittedDraft(aid, cid, text, attachments) {
      const draft = this.getDraft(aid, cid)
      return this.saveDraft(aid, cid, draft.text === text ? '' : draft.text,
        draft.attachments.filter(file => !attachments.includes(file)))
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
      for (const key of Object.keys(this.drafts)) if (key.endsWith(`:${cid}`)) delete this.drafts[key]
      this.clearUnsentChats(cid)
      this.conversations = this.conversations.filter(conversation => conversation.cid !== cid)
      this.conversationsLength = this.conversations.length
    },
    updateConversation(cid, key, value) {
      const index = this.conversations.findIndex(conversation => conversation.cid === cid)
      this.conversations[index][key] = value
    },
  },
})

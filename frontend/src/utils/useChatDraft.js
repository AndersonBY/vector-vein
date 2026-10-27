import { computed, ref, watch, onBeforeMount, onBeforeUnmount, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { chatDraftKey, useUserChatsStore } from '@/stores/userChats'

export function useChatDraft(agentId, conversationId = ref('')) {
  const store = useUserChatsStore()
  const { t } = useI18n()
  const userInput = ref('')
  const attachments = ref([])
  const owner = computed(() => [agentId.value, conversationId.value])
  let restoring = false
  let saving = false
  let disposed = false
  let version = 0
  const reportFailure = () => message.error(t('workspace.chatSpace.draft_save_failed'))
  const restore = draft => {
    restoring = true
    userInput.value = draft.text
    attachments.value = [...draft.attachments]
    restoring = false
  }
  const load = async () => {
    const current = ++version
    const [aid, cid] = owner.value
    restore(store.getDraft(aid, cid))
    try {
      const draft = await store.loadDraft(aid, cid)
      if (!disposed && current === version) restore(draft)
    } catch {
      if (!disposed && current === version) reportFailure()
    }
  }
  const sync = () => {
    if (!restoring && !disposed) {
      const [aid, cid] = owner.value
      saving = true
      void store.saveDraft(aid, cid, userInput.value, [...attachments.value]).catch(reportFailure)
      saving = false
    }
  }
  watch([userInput, attachments], sync, { deep: true, flush: 'sync' })
  watch(() => store.drafts[chatDraftKey(...owner.value)]?.revision, () => {
    const draft = store.drafts[chatDraftKey(...owner.value)]
    if (!saving && draft) restore(draft)
  }, { flush: 'sync' })
  watch(owner, load, { flush: 'sync' })
  onBeforeMount(load)
  // Native screenshot insertion targets the currently visible composer.
  const setAttachments = files => { if (!disposed) attachments.value = files }
  onMounted(() => { window.setAttachments = setAttachments })
  onBeforeUnmount(() => {
    disposed = true
    version++
    if (window.setAttachments === setAttachments) delete window.setAttachments
  })
  return { userInput, attachments, draftOwner: owner }
}

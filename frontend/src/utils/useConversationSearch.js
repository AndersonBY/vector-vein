import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { conversationAPI } from '@/api/chat'

export function useConversationSearch(agentId) {
  const keyword = ref('')
  const results = ref([])
  const total = ref(0)
  const searching = ref(false)
  const failed = ref(false)
  const active = computed(() => Boolean(keyword.value.trim()))
  const hasMore = computed(() => results.value.length < total.value)
  let timer
  let version = 0
  let disposed = false

  const run = async (append = false) => {
    clearTimeout(timer)
    const query = keyword.value.trim()
    const aid = agentId.value
    if (!query || !aid || disposed) return
    const requestVersion = ++version
    const offset = append ? results.value.length : 0
    searching.value = true
    failed.value = false
    try {
      const response = await conversationAPI('search', { aid, query, limit: 20, offset })
      if (disposed || requestVersion !== version) return
      if (response.status !== 200 || !Array.isArray(response.data?.results)) throw new Error('Search failed')
      results.value = append ? [...results.value, ...response.data.results] : response.data.results
      total.value = response.data.total
    } catch {
      if (!disposed && requestVersion === version) failed.value = true
    } finally {
      if (!disposed && requestVersion === version) searching.value = false
    }
  }

  watch([agentId, keyword], () => {
    version++
    clearTimeout(timer)
    results.value = []
    total.value = 0
    failed.value = false
    searching.value = active.value
    if (active.value) timer = setTimeout(() => { void run() }, 300)
  }, { flush: 'sync' })

  onBeforeUnmount(() => {
    disposed = true
    version++
    clearTimeout(timer)
  })

  return { keyword, results, total, searching, failed, active, hasMore,
    loadMore: () => { if (!searching.value) return run(true) } }
}

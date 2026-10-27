import assert from 'node:assert/strict'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, ref, nextTick } from 'vue'
import { createServer } from 'vite'

const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
const flush = async () => { await Promise.resolve(); await Promise.resolve(); await nextTick() }
const response = (results, total = results.length) => ({ status: 200, data: { results, total } })

test('conversation search debounces, invalidates stale requests, paginates and survives retry and disposal', async () => {
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'search-api', resolveId(id) { if (id === '@/api/chat') return '\0search-api' },
      load(id) { if (id === '\0search-api') return 'export const conversationAPI = (...args) => globalThis.__searchRequest(...args)' } }],
    server: { middlewareMode: true, hmr: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  const previousRequest = globalThis.__searchRequest
  const timers = new Map(), calls = []
  let timerId = 0, now = 0
  const previousTimeout = globalThis.setTimeout, previousClear = globalThis.clearTimeout
  try {
    const { useConversationSearch } = await server.ssrLoadModule('/src/utils/useConversationSearch.js')
    globalThis.__searchRequest = (action, payload) => { const pending = deferred(); calls.push({ action, payload, ...pending }); return pending.promise }
    globalThis.setTimeout = (callback, delay) => { const id = ++timerId; timers.set(id, { callback, time: now + delay }); return id }
    globalThis.clearTimeout = id => timers.delete(id)
    const advance = async ms => { now += ms; for (const [id, task] of [...timers]) if (task.time <= now) { timers.delete(id); task.callback() } await flush() }
    const renderer = createRenderer({ createElement: () => ({}), insert() {}, remove() {}, setElementText() {},
      createText: () => ({}), createComment: () => ({}), setText() {}, setComment() {}, parentNode() {}, nextSibling() {}, patchProp() {} })
    const aid = ref('agent-one')
    let search
    const app = renderer.createApp({ setup() { search = useConversationSearch(aid); return () => h('div') } })
    app.mount({})
    search.keyword.value = 'n'
    await advance(200)
    search.keyword.value = 'needle'
    await advance(299)
    assert.equal(calls.length, 0)
    await advance(1)
    assert.deepEqual(calls[0].payload, { aid: 'agent-one', query: 'needle', limit: 20, offset: 0 })
    // Even edits with the same normalized query invalidate an in-flight response.
    search.keyword.value = ' needle '
    calls[0].resolve(response([{ cid: 'stale' }]))
    await flush()
    assert.deepEqual(search.results.value, [])
    await advance(300)
    const firstPage = Array.from({ length: 20 }, (_, i) => ({ cid: `cid-${i}` }))
    calls[1].resolve(response(firstPage, 23))
    await flush()
    assert.equal(search.results.value.length, 20)
    assert.equal(search.hasMore.value, true)
    const failedPage = search.loadMore()
    assert.equal(calls[2].payload.offset, 20)
    calls[2].resolve({ status: 500 })
    await failedPage
    assert.equal(search.failed.value, true)
    assert.equal(search.results.value.length, 20)
    const retry = search.loadMore()
    assert.equal(calls[3].payload.offset, 20)
    calls[3].resolve(response([{ cid: '20' }, { cid: '21' }, { cid: '22' }], 23))
    await retry
    assert.equal(search.results.value.length, 23)
    assert.equal(search.hasMore.value, false)
    assert.equal(search.failed.value, false)
    search.keyword.value = 'other'
    await advance(300)
    search.keyword.value = ''
    calls[4].resolve(response([{ cid: 'cleared' }]))
    await flush()
    assert.equal(search.active.value, false)
    assert.equal(search.searching.value, false)
    assert.deepEqual(search.results.value, [])
    search.keyword.value = 'agent search'
    await advance(300)
    aid.value = 'agent-two'
    calls[5].resolve(response([{ cid: 'wrong-agent' }]))
    await flush()
    assert.deepEqual(search.results.value, [])
    await advance(300)
    assert.equal(calls[6].payload.aid, 'agent-two')
    app.unmount()
    calls[6].resolve(response([{ cid: 'unmounted' }]))
    await flush()
    assert.deepEqual(search.results.value, [])
    assert.equal(timers.size, 0)
    const pendingApp = renderer.createApp({ setup() { search = useConversationSearch(aid); return () => h('div') } })
    pendingApp.mount({})
    search.keyword.value = 'leave before debounce'
    assert.equal(timers.size, 1)
    pendingApp.unmount()
    await advance(300)
    assert.equal(timers.size, 0)
    assert.equal(calls.length, 7)
  } finally {
    globalThis.setTimeout = previousTimeout
    globalThis.clearTimeout = previousClear
    if (previousRequest === undefined) delete globalThis.__searchRequest
    else globalThis.__searchRequest = previousRequest
    await server.close()
  }
})

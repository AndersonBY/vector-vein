import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick, reactive } from 'vue'
import { createI18n } from 'vue-i18n'
import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'
import { createServer } from 'vite'
import { folderOptions, knowledgeOptions, validChunkSettings, indexingErrorKey } from '../src/utils/knowledgeBase.js'

const flush = async () => { for (let i = 0; i < 5; i++) await new Promise(resolve => setImmediate(resolve)); await nextTick() }
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const source = file => readFile(new URL(`../src/${file}`, import.meta.url), 'utf8')
const base = { id: 'base', name: 'Research', document_count: 1 }
const item = { id: 'doc', name: 'Source.txt', kind: 'file', path: '/Source.txt', status: 'ready', updated_at: 'revision' }

async function withDetail(run) {
  const filename = fileURLToPath(new URL('../src/views/Workspace/Database/KnowledgeBaseDetail.vue', import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const compiled = compileScript(descriptor, { id: 'knowledge-detail' }).content
    .replace("'@/components/IconButton.vue'", "'virtual:icon-button'").replace("'@/icons'", "'virtual:icons'")
    .replace("'@/api/knowledgeBase'", "'virtual:api'").replace("'vue-router'", "'virtual:router'").replace("'ant-design-vue'", "'virtual:ant'")
  const state = {
    route: reactive({ params: { kbId: 'base' } }), calls: [], notices: [], confirmations: [], timers: [],
    handler: async action => ({ get: base, tree: { folders: [] }, items: { items: [item], breadcrumbs: [], total: 1 }, preview: { item, text: 'Source text' }, search: { results: [], warnings: [] } })[action] || {},
  }
  globalThis.__knowledgeTest = state
  const modules = {
    'virtual:icon-button': 'export default {}',
    'virtual:icons': 'export const Refresh={},Redo={},Upload={},FolderOpen={},Add={},More={},OpenExternal={}',
    '/detail.js': `${compiled}
      const setTimeout = callback => { const timer = { callback }; globalThis.__knowledgeTest.timers.push(timer); return timer }
      const clearTimeout = timer => { if (timer) timer.cancelled = true }`,
    'virtual:api': `export const knowledgeErrorKey = () => 'knowledgeBase.operation_failed'; export const knowledgeRequest = (action,payload) => { const state = globalThis.__knowledgeTest; state.calls.push({action,payload:structuredClone(payload)}); return state.handler(action,payload) }`,
    'virtual:router': 'export const useRoute = () => globalThis.__knowledgeTest.route',
    'virtual:ant': `export const message = Object.fromEntries(['success','error','warning'].map(key => [key, text => globalThis.__knowledgeTest.notices.push({key,text})])); export const Modal = { confirm: value => globalThis.__knowledgeTest.confirmations.push(value) }`,
  }
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'knowledge-fixture', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  let app, vm
  try {
    const component = (await server.ssrLoadModule('/detail.js')).default
    const renderer = createRenderer({ createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {}, parentNode: () => null, nextSibling: () => null })
    app = renderer.createApp({ setup(props, context) { vm = component.setup(props, context); return () => h('div') } })
    const messages = JSON.parse(await source('locales/en-US.json'))
    app.use(createI18n({ legacy: false, locale: 'en-US', messages: { 'en-US': messages } }))
    app.mount({}); await flush()
    await run({ vm, state, unmount: () => { app.unmount(); app = null } })
  } finally { app?.unmount(); await server.close(); delete globalThis.__knowledgeTest; delete globalThis.window }
}

test('folder destinations exclude the entire moved subtree and mounts preserve missing selections', () => {
  const tree = [{ id: 'a', name: 'A', children: [{ id: 'b', name: 'B', children: [] }] }, { id: 'c', name: 'C' }]
  assert.deepEqual(folderOptions(tree, 'a'), [{ value: 'c', label: 'C' }])
  assert.equal(folderOptions(tree)[1].label, 'A / B')
  assert.deepEqual(knowledgeOptions([base], ['base', 'gone', 'gone'], id => `Missing ${id}`), [
    { value: 'base', label: 'Research' }, { value: 'gone', label: 'Missing gone', disabled: true },
  ])
  assert.equal(validChunkSettings(1000, 200), true)
  for (const pair of [[0, 0], [100, 100], [100, -1], [1.2, 0], [100, null]]) assert.equal(validChunkSettings(...pair), false)
})

test('KB browser scopes folders, pagination and content search using documented payloads', async () => {
  await withDetail(async ({ vm, state }) => {
    vm.navigate('folder'); await flush()
    assert.deepEqual(state.calls.filter(call => call.action === 'items').at(-1).payload, { kb_id: 'base', parent_id: 'folder', search: '', offset: 0, limit: 50 })
    vm.page.value = 3; await vm.load()
    assert.equal(state.calls.filter(call => call.action === 'items').at(-1).payload.offset, 100)
    vm.searchQuery.value = ' 中文 '; vm.searchMode.value = 'keyword'; await vm.search()
    assert.deepEqual(state.calls.at(-1), { action: 'search', payload: { kb_ids: ['base'], query: '中文', mode: 'keyword', folder_id: 'folder', limit: 20 } })
    vm.navigate('__root__'); await flush()
    assert.equal(vm.parentId.value, null)
    assert.equal(vm.page.value, 1)
  })
})

test('native imports preserve source path and destination; cancellation submits nothing', async () => {
  await withDetail(async ({ vm, state }) => {
    globalThis.window = { pywebview: { api: { open_file_dialog: async multiple => { assert.equal(multiple, true); return ['C:\\Docs\\A.txt'] }, open_folder_dialog: async () => 'C:\\Docs\\Nested' } } }
    vm.parentId.value = 'folder'
    await vm.importNative(false)
    assert.deepEqual(state.calls.find(call => call.action === 'import_files').payload, { kb_id: 'base', parent_id: 'folder', paths: ['C:\\Docs\\A.txt'] })
    await vm.importNative(true)
    assert.deepEqual(state.calls.find(call => call.action === 'import_directory').payload, { kb_id: 'base', parent_id: 'folder', path: 'C:\\Docs\\Nested' })
    window.pywebview.api.open_file_dialog = async () => []
    const before = state.calls.length
    await vm.importNative(false)
    assert.equal(state.calls.length, before)
  })
})

test('rename, move and confirmed recursive deletion include revision tokens', async () => {
  await withDetail(async ({ vm, state }) => {
    vm.edit('rename', item); vm.name.value = ' Renamed.txt '; await vm.saveDialog()
    assert.deepEqual(state.calls.find(call => call.action === 'rename').payload, { kb_id: 'base', id: 'doc', expected_updated_at: 'revision', name: 'Renamed.txt' })
    vm.edit('move', item); vm.destination.value = '__root__'; await vm.saveDialog()
    assert.deepEqual(state.calls.find(call => call.action === 'move').payload, { kb_id: 'base', id: 'doc', expected_updated_at: 'revision', parent_id: null })
    vm.remove(item)
    assert.equal(state.calls.some(call => call.action === 'delete_item'), false)
    await state.confirmations.at(-1).onOk()
    assert.deepEqual(state.calls.find(call => call.action === 'delete_item').payload, { kb_id: 'base', id: 'doc', expected_updated_at: 'revision' })
    vm.reindex(item)
    await state.confirmations.at(-1).onOk()
    assert.deepEqual(state.calls.find(call => call.action === 'reindex').payload, { kb_id: 'base', id: 'doc' })
  })
})

test('preview hydration ignores old selections and unmounted requests; failures show safe copy', async () => {
  await withDetail(async ({ vm, state, unmount }) => {
    const old = deferred()
    state.handler = (action, payload) => action === 'preview' && payload.id === 'old' ? old.promise : Promise.resolve({ item: { ...item, id: payload.id }, text: 'Current text' })
    const pending = vm.openPreview({ ...item, id: 'old' })
    await vm.openPreview(item)
    old.resolve({ item: { ...item, id: 'old' }, text: 'Old text' }); await pending
    assert.equal(vm.preview.value.item.id, 'doc')
    state.handler = async () => { throw new Error('provider credential secret') }
    assert.equal(await vm.mutate('rename', { id: 'doc', name: 'x' }), false)
    assert.equal(state.notices.at(-1).key, 'error')
    assert.equal(state.notices.at(-1).text.includes('secret'), false)
    const late = deferred(); state.handler = () => late.promise
    const lateRequest = vm.openPreview(item); unmount()
    late.resolve({ item, text: 'Late text' }); await lateRequest
    assert.equal(vm.preview.value.text, '')
  })
})

test('content search failures and degraded retrieval have distinct safe states', async () => {
  await withDetail(async ({ vm, state }) => {
    vm.searchQuery.value = 'source'
    state.handler = async () => ({ results: [{ document_id: 'doc', text: 'hit' }], warnings: ['private provider detail'] })
    await vm.search()
    assert.equal(vm.results.value[0].document_id, 'doc')
    assert.equal(vm.warnings.value.length, 1)
    state.handler = async () => { throw new Error('private provider detail') }
    await vm.search()
    assert.equal(vm.searchFailed.value, true)
    assert.deepEqual(vm.results.value, [])
  })
})

test('native picker rejects duplicate clicks while the operating-system dialog is pending', async () => {
  await withDetail(async ({ vm, state }) => {
    const picker = deferred()
    let opened = 0
    globalThis.window = { pywebview: { api: { open_file_dialog: () => { opened++; return picker.promise } } } }
    const pending = vm.importNative(false)
    assert.equal(vm.picking.value, true)
    await vm.importNative(false)
    assert.equal(opened, 1)
    picker.resolve([]); await pending
    assert.equal(vm.picking.value, false)
    assert.equal(state.calls.some(call => call.action === 'import_files'), false)
  })
})

test('polling retries transient errors and publishes extracted text after embedding failure', async () => {
  await withDetail(async ({ vm, state }) => {
    const original = state.handler
    let failed = true
    state.handler = async (action, payload) => {
      if (action === 'get' && failed) throw new Error('transient')
      if (action === 'preview') return { item: { ...item, status: 'indexing', updated_at: 'old' }, text: '' }
      return original(action, payload)
    }
    await vm.load(true)
    assert.equal(vm.failed.value, true)
    assert.equal(state.timers.at(-1).cancelled, undefined)
    failed = false
    await state.timers.at(-1).callback()
    assert.equal(vm.failed.value, false)
    await vm.openPreview({ ...item, status: 'indexing' })
    vm.rightTab.value = 'search'
    state.handler = async (action, payload) => {
      if (action === 'items') return { items: [{ ...item, status: 'failed', error_code: 'embedding_unavailable', updated_at: 'new' }], total: 1, breadcrumbs: [] }
      if (action === 'preview') return { item: { ...item, status: 'failed', error_code: 'embedding_unavailable', updated_at: 'new' }, text: 'Extracted text survives embedding failure' }
      return original(action, payload)
    }
    await vm.load(true); await flush()
    assert.match(vm.preview.value.text, /survives/)
    assert.equal(vm.rightTab.value, 'search', 'background indexing completion does not change the active pane')
    assert.equal(indexingErrorKey(vm.preview.value.item.error_code), 'knowledgeBase.embedding_unavailable')
    for (const code of ['embedding_failed', 'extraction_failed', 'empty_document', 'text_too_large', 'file_too_large']) assert.equal(indexingErrorKey(code), `knowledgeBase.${code}`)
    assert.equal(indexingErrorKey('private exception'), 'knowledgeBase.index_failed')
    assert.equal(indexingErrorKey('invalid_embedding'), 'knowledgeBase.invalid_embedding')
    assert.equal(indexingErrorKey('indexing_failed'), 'knowledgeBase.index_failed')
    assert.equal(vm.canConfigureEmbedding('embedding_unavailable'), true)
    assert.equal(vm.canConfigureEmbedding('invalid_embedding'), true)
    assert.equal(vm.canConfigureEmbedding('empty_document'), false)
  })
})

test('conflict refresh preserves rename draft and renews revision; stale delete requires a new confirmation', async () => {
  await withDetail(async ({ vm, state }) => {
    const original = state.handler
    let conflict = true
    state.handler = async (action, payload) => {
      if (['rename', 'delete_item'].includes(action) && conflict) { const error = new Error('changed'); error.code = 'conflict'; throw error }
      if (action === 'items') return { items: [{ ...item, updated_at: 'fresh' }], total: 1, breadcrumbs: [] }
      return original(action, payload)
    }
    vm.edit('rename', item); vm.name.value = 'My draft.txt'
    await vm.saveDialog()
    assert.equal(vm.dialog.value, 'rename')
    assert.equal(vm.name.value, 'My draft.txt')
    assert.equal(vm.target.value.updated_at, 'fresh')
    conflict = false; await vm.saveDialog()
    assert.equal(state.calls.filter(call => call.action === 'rename').at(-1).payload.expected_updated_at, 'fresh')
    conflict = true; vm.remove(item)
    await state.confirmations.at(-1).onOk()
    assert.equal(vm.operationConflict.value, true)
    conflict = false; vm.remove(vm.items.value[0])
    await state.confirmations.at(-1).onOk()
    assert.equal(state.calls.filter(call => call.action === 'delete_item').at(-1).payload.expected_updated_at, 'fresh')
  })
})

test('navigation invalidates pending folder search and old confirmation dialogs', async () => {
  await withDetail(async ({ vm, state }) => {
    const late = deferred()
    const original = state.handler
    state.handler = (action, payload) => action === 'search' ? late.promise : original(action, payload)
    vm.searchQuery.value = 'source'
    const pending = vm.search()
    vm.navigate('another-folder'); await flush()
    late.resolve({ results: [{ document_id: 'old-scope' }] }); await pending
    assert.deepEqual(vm.results.value, [])
    vm.reindex()
    const confirmation = state.confirmations.at(-1)
    state.route.params.kbId = 'another-base'; await flush()
    await confirmation.onOk()
    assert.equal(state.calls.some(call => call.action === 'reindex'), false)
    assert.equal(vm.searchQuery.value, '')
  })
})

test('route exit cancels polling and pending loads without sending empty knowledge-base IDs', async () => {
  await withDetail(async ({ vm, state }) => {
    const timer = state.timers.at(-1)
    const late = deferred(), original = state.handler
    state.handler = (action, payload) => action === 'get' ? late.promise : original(action, payload)
    const pending = vm.load()
    const count = state.calls.length, timerCount = state.timers.length
    state.route.params = {}
    await flush()
    assert.equal(timer.cancelled, true)
    assert.equal(vm.loading.value, false)
    assert.equal(vm.base.value, null)
    assert.deepEqual(vm.items.value, [])
    assert.equal(state.calls.length, count, 'route exit must not start get/tree/items requests')
    late.resolve({ ...base, name: 'Stale response' }); await pending
    assert.equal(vm.base.value, null, 'old scope cannot hydrate the exited view')
    await timer.callback()
    await vm.load()
    assert.equal(state.calls.length, count, 'late polling and explicit loads also reject empty scope')
    assert.equal(state.timers.length, timerCount, 'exited scopes never reschedule polling')
    assert.ok(state.calls.every(call => Boolean(call.action === 'get' ? call.payload.id : call.payload.kb_id)))
  })
})

test('API uses the fixed namespace and exposes safe error codes without provider exceptions', async () => {
  const calls = []
  globalThis.__knowledgeAPI = async (...args) => { calls.push(args); return { status: 200, data: { bases: [base] } } }
  const apiSource = (await source('api/knowledgeBase.js')).replace("import baseAPI from './base'", 'const baseAPI = (...args) => globalThis.__knowledgeAPI(...args)')
  try {
    const api = await import(`data:text/javascript;base64,${Buffer.from(apiSource).toString('base64')}`)
    assert.deepEqual(await api.knowledgeRequest('list'), { bases: [base] })
    assert.deepEqual(calls[0], ['knowledge_base__list', {}])
    globalThis.__knowledgeAPI = async () => ({ status: 409, data: { error_code: 'conflict' }, msg: 'secret provider exception' })
    await assert.rejects(api.knowledgeRequest('rename', {}), error => error.message === 'knowledge_request_failed' && error.code === 'conflict')
    assert.equal(api.knowledgeErrorKey({ code: 'conflict' }), 'knowledgeBase.conflict')
    assert.equal(api.knowledgeErrorKey({ code: 'secret provider exception' }), 'knowledgeBase.operation_failed')
  } finally { delete globalThis.__knowledgeAPI }
})

test('KB templates compile, bilingual keys match and standalone vector screens are retired', async () => {
  const en = JSON.parse(await source('locales/en-US.json')), zh = JSON.parse(await source('locales/zh-CN.json'))
  assert.deepEqual(Object.keys(en.knowledgeBase).sort(), Object.keys(zh.knowledgeBase).sort())
  for (const file of ['views/Workspace/Database/KnowledgeBaseDetail.vue', 'components/workspace/database/KnowledgeBaseCatalog.vue', 'components/taskAgent/KnowledgeBasePicker.vue']) {
    const content = await source(file)
    const { descriptor } = parse(content)
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: file, id: file }).errors, [])
    for (const [, key] of content.matchAll(/t\('knowledgeBase\.([a-z_]+)'(?!\s*\+)/g)) assert.ok(en.knowledgeBase[key], key)
    assert.doesNotMatch(content, /message\.error\([^)]*(?:error\.message|response\.msg)/)
  }
  const routes = await source('router/modules/data.js')
  assert.doesNotMatch(routes, /VectorDatabase|DocumentQueryTest/)
  assert.match(routes, /RelationalDatabaseDetail/)
  assert.match(await source('api/knowledgeBase.js'), /knowledge_base__\$\{action\}/)
  assert.match(await source('views/Workspace/TaskAgent/TaskAgentAgentDetail.vue'), /v-model="draft\.knowledge_base_ids"/)
  assert.doesNotMatch(await source('views/Workspace/TaskAgent/TaskAgentWorkbench.vue'), /KnowledgeBasePicker/, 'workbench does not show the removed knowledge-base picker')
  assert.match(await source('views/Workspace/TaskAgent/TaskAgentDetail.vue'), /config_snapshot\.knowledge_bases/)
  const catalog = await source('components/workspace/database/KnowledgeBaseCatalog.vue')
  assert.equal([...catalog.matchAll(/chunk_size: 1000, chunk_overlap: 150/g)].length, 2, 'initial and reset create defaults match the backend')
  assert.match(catalog, /name: 'settings', query: \{ section: 'embedding_models' \}/)
  assert.match(await source('views/Workspace/Database/KnowledgeBaseDetail.vue'), /name: 'settings', query: \{ section: 'embedding_models' \}/)
})


test('invalid search queries show actionable validation instead of a clean empty result and clear on the next search', async () => {
  await withDetail(async ({ vm, state }) => {
    const original = state.handler
    state.handler = async (action, payload) => {
      if (action === 'search' && payload.query === '*') {
        const error = new Error('invalid_query'); error.code = 'invalid_query'; throw error
      }
      if (action === 'search') return { results: [{ document_id: 'matched-document' }], warnings: [] }
      return original(action, payload)
    }
    vm.searchQuery.value = '*'
    await vm.search()
    assert.equal(vm.searchFailed.value, true)
    assert.equal(vm.searchErrorCode.value, 'invalid_query')
    assert.deepEqual(vm.results.value, [])
    vm.searchQuery.value = 'source'
    await vm.search()
    assert.equal(vm.searchFailed.value, false)
    assert.equal(vm.searchErrorCode.value, '')
    assert.equal(vm.results.value[0].document_id, 'matched-document')
    vm.navigate(null); await flush()
    assert.equal(vm.searchErrorCode.value, '')
  })
})

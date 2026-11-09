import { iconButtonFixture } from './taskAgentButtonFixture.js'
import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick, reactive } from 'vue'
import { createI18n } from 'vue-i18n'
import { compileScript, parse } from 'vue/compiler-sfc'
import { createServer } from 'vite'

const flush = async () => { for (let i = 0; i < 5; i++) await new Promise(resolve => setImmediate(resolve)); await nextTick() }
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const agent = (id, extra = {}) => ({ agent_id: id, name: id, description: `Description ${id}`, ...extra })
const task = (id, extra = {}) => ({ tid: id, title: id, goal: `Goal ${id}`, status: 'COMPLETED', ...extra })

async function withPicker(kind, run, overrides = {}) {
  const filename = fileURLToPath(new URL(`../src/components/taskAgent/${kind}Picker.vue`, import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const source = compileScript(descriptor, { id: `${kind}-picker` }).content.replace("'@/components/IconButton.vue'", "'virtual:icon-button'").replace("'./PickerModal.vue'", "'virtual:modal'").replace("'@/api/taskAgent'", "'virtual:api'").replace("'@/icons'", "'virtual:icons'")
  const calls = [], events = []
  const state = {
    handler: async action => action === 'profiles' ? { status: 200, data: { agents: [agent('general')] } } :
      action === 'projects' ? { status: 200, data: { projects: [] } } : { status: 200, data: { tasks: [task('one')], total: 1 } },
  }
  globalThis.__pickerTest = { calls, state }
  const modules = {
    'virtual:icon-button': iconButtonFixture,
    '/picker.js': source,
    'virtual:modal': 'export default { render: () => null }',
    'virtual:icons': 'export const Robot = { render: () => null }, Right = Robot, CheckOne = Robot, ListOne = Robot; export const Refresh=Robot,Close=Robot,Delete=Robot,Undo=Robot,Star=Robot,OffScreenOne=Robot,Down=Robot,OpenExternal=Robot;',
    'virtual:api': 'export const taskAgentAPI = (action,payload) => { const {calls,state} = globalThis.__pickerTest; calls.push({action,payload:structuredClone(payload)}); return state.handler(action,payload) }',
  }
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'picker-fixture', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  let app, vm
  const props = reactive({ modelValue: '', agents: null, disabled: false, compact: false, allowClear: true, placeholder: '', selectedTask: undefined, visibility: 'all', ...overrides })
  try {
    const component = (await server.ssrLoadModule('/picker.js')).default
    const renderer = createRenderer({ createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {}, parentNode: () => null, nextSibling: () => null })
    app = renderer.createApp({
      setup(_props, context) {
        vm = component.setup(props, { ...context, emit: (...args) => events.push(args) })
        return () => h('div')
      },
    })
    const messages = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
    app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } }))
    app.mount({}); await flush()
    await run({ vm, props, calls, events, state, unmount: () => { app.unmount(); app = null } })
  } finally { app?.unmount(); await server.close(); delete globalThis.__pickerTest }
}

test('Agent picker searches and filters the catalog, cancels drafts and only commits confirmation', async () => {
  await withPicker('Agent', async ({ vm, props, events, calls }) => {
    vm.show()
    vm.search.value = 'SHELL'
    assert.deepEqual(vm.filtered.value.map(a => a.agent_id), ['writer'])
    vm.search.value = ''; vm.filter.value = 'skills'
    assert.deepEqual(vm.filtered.value.map(a => a.agent_id), ['research'])
    vm.draftId.value = 'research'
    vm.close()
    assert.deepEqual(events, [])
    vm.show()
    assert.equal(vm.draftId.value, 'general')
    vm.draftId.value = 'writer'; vm.confirm()
    assert.equal(events[0][0], 'update:modelValue')
    assert.equal(events[0][1], 'writer')
    assert.equal(events[1][2].allow_shell, true)
    assert.equal(calls.length, 0, 'provided catalogs do not cause extra API calls')
    props.disabled = true; await flush(); vm.show(); vm.clear()
    assert.equal(vm.open.value, false)
    assert.equal(events.length, 2)
  }, { modelValue: 'general', agents: [agent('general'), agent('writer', { description: 'Shell expert', allow_shell: true }), agent('research', { skill_ids: ['search'] })] })
})

test('Agent picker paginates filtered results and retries failed catalog requests', async () => {
  await withPicker('Agent', async ({ vm, state }) => {
    state.handler = async () => ({ status: 503 })
    vm.show(); await flush()
    assert.equal(vm.failed.value, true)
    state.handler = async () => ({ status: 200, data: { agents: Array.from({ length: 23 }, (_, i) => agent(`agent-${i}`)) } })
    await vm.load()
    assert.equal(vm.filtered.value.length, 23)
    vm.page.value = 3
    assert.equal(vm.visible.value.length, 3)
    vm.search.value = 'agent-1'; await flush()
    assert.equal(vm.currentPage.value, 1)
    assert.equal(vm.filtered.value.length, 11)
    const slow = deferred()
    state.handler = () => slow.promise
    const pending = vm.load(); vm.close()
    slow.resolve({ status: 200, data: { agents: [] } }); await pending
    assert.equal(vm.available.value.length, 23, 'closed requests cannot replace the catalog')
  })
})

test('standalone picker labels ignore late hydration for a previous selection', async () => {
  for (const kind of ['Agent', 'Task']) {
    await withPicker(kind, async ({ vm, props, state }) => {
      const old = deferred()
      state.handler = async (_action, payload) => {
        const id = payload.agent_id || payload.task_id
        if (id === 'old') return old.promise
        return { status: 200, data: kind === 'Agent' ? agent(id) : { task: task(id) } }
      }
      props.modelValue = 'old'; await flush()
      props.modelValue = 'new'; await flush()
      old.resolve({ status: 200, data: kind === 'Agent' ? agent('old') : { task: task('old') } }); await flush()
      assert.equal(vm.label.value, 'new')
    })
  }
})

test('Task picker includes hidden tasks, filters on the server and uses page offsets independent of selected history', async () => {
  await withPicker('Task', async ({ vm, calls, state, events }) => {
    state.handler = async (action, payload) => action === 'list' ?
      { status: 200, data: { tasks: [task(`listed-${payload.offset}`, { hidden: 1 })], total: 45 } } :
      action === 'profiles' ? { status: 200, data: { agents: [agent('research')] } } :
      { status: 200, data: { projects: [{ project_id: 'alpha', name: 'Alpha' }] } }
    vm.show(); await flush()
    assert.equal(calls.find(c => c.action === 'list').payload.visibility, 'all')
    assert.equal(calls.some(c => c.action === 'get'), false, 'caller-supplied task details are reused')
    vm.page.value = 2; await delay(10); await flush()
    assert.equal(calls.filter(c => c.action === 'list').at(-1).payload.offset, 20)
    vm.agentId.value = 'research'; vm.projectId.value = 'alpha'; vm.status.value = 'FAILED'; vm.visibilityFilter.value = 'hidden'
    await delay(10); await flush()
    const query = calls.filter(c => c.action === 'list').at(-1).payload
    assert.equal(query.offset, 0)
    assert.equal(query.agent_id, 'research')
    assert.equal(query.project_id, 'alpha')
    assert.deepEqual(query.statuses, ['FAILED'])
    assert.equal(query.visibility, 'hidden')
    vm.draft.value = vm.tasks.value[0]; vm.confirm()
    assert.equal(events[0][1], 'listed-0')
    assert.equal(events[1][2].hidden, 1)
    assert.equal(vm.open.value, false)
  }, { modelValue: 'historic', selectedTask: task('historic') })
})

test('Task picker debounces search, rejects stale pages, preserves cancellation and retries errors', async () => {
  await withPicker('Task', async ({ vm, calls, events, state }) => {
    vm.show(); await flush()
    const slow = deferred(), handler = state.handler
    state.handler = (action, payload) => action === 'list' && payload.search === 'slow' ? slow.promise : handler(action, payload)
    vm.search.value = 'slow'; await delay(230); await flush()
    vm.search.value = 'unused'; vm.search.value = 'fast'; await delay(230); await flush()
    assert.equal(calls.some(c => c.action === 'list' && c.payload.search === 'unused'), false)
    slow.resolve({ status: 200, data: { tasks: [task('stale')], total: 1 } }); await flush()
    assert.equal(vm.tasks.value[0].tid, 'one')
    vm.draft.value = task('one'); vm.close()
    assert.deepEqual(events, [])
    vm.show(); await flush()
    assert.equal(vm.draft.value, null)
    state.handler = async () => ({ status: 500 })
    await vm.load(); assert.equal(vm.failed.value, true)
    state.handler = handler
    await vm.load(); assert.equal(vm.failed.value, false)
    vm.search.value = 'after-unmount'
    const count = calls.length
    vm.close(); await delay(230)
    assert.equal(calls.length, count)
  })
})

test('Task picker resolves a saved selection that finishes loading after the modal opens', async () => {
  await withPicker('Task', async ({ vm, props }) => {
    vm.show()
    assert.equal(vm.draft.value, null)
    props.selectedTask = task('saved')
    await flush()
    assert.equal(vm.draft.value.tid, 'saved')
    vm.draft.value = task('explicit')
    props.selectedTask = task('saved', { title: 'Updated title' })
    await flush()
    assert.equal(vm.draft.value.tid, 'explicit', 'hydration must not replace a user choice')
  }, { modelValue: 'saved', selectedTask: null })
})

test('global scrollbars use the reference dimensions and no component overrides them', async () => {
  const css = await readFile(new URL('../src/assets/css/scrollbar.css', import.meta.url), 'utf8')
  assert.match(css, /\*::-webkit-scrollbar\s*\{\s*width: 6px;\s*height: 6px;/)
  assert.match(css, /--scrollbar-thumb: #ccc/)
  assert.match(css, /rgba\(255, 255, 255, 0\.22\)/)
  assert.match(css, /@supports not selector\(::-webkit-scrollbar\)/)
  for (const name of ['App.vue', 'components/CodeEditorModal.vue', 'components/workspace/database/SQLInteract.vue', 'layouts/WorkspaceLayout.vue', 'views/Workspace/WorkflowEditor.vue']) {
    assert.doesNotMatch(await readFile(new URL(`../src/${name}`, import.meta.url), 'utf8'), /::-webkit-scrollbar/)
  }
})

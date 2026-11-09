import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick } from 'vue'
import { createI18n } from 'vue-i18n'
import { compileScript, parse } from 'vue/compiler-sfc'
import { createServer } from 'vite'

test('schedule manager preserves saved timezone and intervals, blocks invalid/double saves and retains failed drafts', async () => {
  const filename = fileURLToPath(new URL('../src/views/Workspace/WorkflowScheduleManager.vue', import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const modules = {
    '@/components/IconButton.vue': 'export default {}',
    '@/icons': 'export const Add={},Edit={},Time={},Delete={}',
    '/schedule-manager.js': compileScript(descriptor, { id: 'schedule-manager' }).content.replace("'vue-router'", "'virtual:schedule-router'").replace("'ant-design-vue'", "'virtual:schedule-ant'"),
    'virtual:schedule-router': 'export const useRoute=()=>({query:{}});export const useRouter=()=>({push:()=>{}})',
    'virtual:schedule-ant': 'export const message={error:x=>globalThis.__scheduleTest.errors.push(x),success:()=>{},warning:()=>{}};export const Modal={confirm:()=>{}}',
    '@/stores/userWorkflows': 'export const useUserWorkflowsStore=()=>({userWorkflows:[{wid:"wf",title:"Workflow"}],refreshWorkflows:async()=>{}})',
    '@/api/workflow': 'export const workflowScheduleTriggerAPI=(a,p)=>{const s=globalThis.__scheduleTest;s.calls.push({action:a,payload:JSON.parse(JSON.stringify(p))});return s.request(a,p)}',
    '@/utils/util': 'export const formatTime=String',
    '@/utils/schedule': 'export const formatSchedule=()=>"Daily"',
    '@/components/scheduling/ScheduleEditor.vue': 'export default {}',
    '@/components/workspace/WorkspacePageHero.vue': 'export default {}',
    '@/components/workspace/WorkspaceEmptyState.vue': 'export default {}',
  }
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'schedule-manager-test', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }],
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  const state = { calls: [], errors: [], request: async () => ({ status: 200, data: { schedules: [], total: 0, page: 1, page_size: 10 } }) }
  globalThis.__scheduleTest = state
  let app, vm
  const flush = async () => { for (let i = 0; i < 6; i++) await nextTick() }
  try {
    const component = (await server.ssrLoadModule('/schedule-manager.js')).default
    const renderer = createRenderer({ createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {}, parentNode: () => null, nextSibling: () => null })
    app = renderer.createApp({ setup(props, context) { vm = component.setup(props, context); return () => h('main') } })
    const messages = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
    app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } }))
    app.mount({}); await flush()
    const recurrence = { unit: 'week', interval: 2, anchor_date: '2026-11-06' }
    vm.openEditModal({ sid: 's1', workflow: { wid: 'wf' }, cron_expression: '30 9 * * 1,5', data: { timezone: 'America/New_York', recurrence } })
    vm.scheduleValid.value = false
    await vm.saveSchedule()
    assert.equal(state.calls.filter(call => call.action === 'update').length, 0)
    vm.scheduleValid.value = true
    state.request = async () => { throw new Error('Disposable network failure') }
    await vm.saveSchedule()
    assert.equal(vm.scheduleModal.open, true)
    assert.equal(vm.saving.value, false)
    assert.equal(vm.scheduleModal.timezone, 'America/New_York')
    assert.deepEqual(state.calls.at(-1).payload, { sid: 's1', wid: 'wf', cron_expression: '30 9 * * 1,5', timezone: 'America/New_York', recurrence })
    let finish
    state.request = async action => action === 'update' ? new Promise(resolve => { finish = resolve }) : ({ status: 200, data: { schedules: [], total: 0, page: 1, page_size: 10 } })
    const pending = vm.saveSchedule()
    await vm.saveSchedule()
    assert.equal(state.calls.filter(call => call.action === 'update').length, 2)
    finish({ status: 200 }); await pending
    assert.equal(vm.scheduleModal.open, false)
    assert.equal(vm.saving.value, false)
    vm.openCreateModal()
    assert.equal(vm.scheduleModal.sid, '')
    assert.equal(vm.scheduleModal.recurrence, null)
    assert.equal(vm.scheduleModal.timezone, Intl.DateTimeFormat().resolvedOptions().timeZone)
    vm.openEditModal({ sid: 'legacy', cron_expression: '0 9 * * *' })
    assert.equal(vm.scheduleModal.timezone, 'Asia/Shanghai', 'missing legacy timezone means server default')
  } finally { app?.unmount(); await server.close(); delete globalThis.__scheduleTest }
})

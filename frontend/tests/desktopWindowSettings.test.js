import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick } from 'vue'
import { createI18n } from 'vue-i18n'
import { compileScript, parse } from 'vue/compiler-sfc'
import { createServer } from 'vite'

const flush = async () => { for (let i = 0; i < 6; i++) await new Promise(resolve => setImmediate(resolve)); await nextTick() }
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

async function settings(run) {
  const filename = fileURLToPath(new URL('../src/components/settings/DesktopWindowSettings.vue', import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const script = compileScript(descriptor, { id: 'desktop-settings' }).content
    .replace("'@/icons'", "'virtual:icons'").replace("'@/components/IconButton.vue'", "'virtual:child'")
    .replace("'ant-design-vue'", "'virtual:ant'").replace("'@/api/user'", "'virtual:api'")
  const state = {
    calls: [], errors: [], successes: [],
    stored: { close_action: 'ask', tray_available: true },
  }
  state.handler = async (action, payload) => {
    if (action === 'update_window_setting') state.stored.close_action = payload.close_action
    return { status: 200, data: structuredClone(state.stored) }
  }
  globalThis.__desktopSettingsTest = state
  const previousWindow = globalThis.window, listeners = new Map()
  globalThis.window = { addEventListener: (name, callback) => listeners.set(name, callback), removeEventListener: name => listeners.delete(name) }
  const modules = {
    '/desktop-settings.js': script,
    'virtual:icons': 'export const Refresh={render:()=>null}',
    'virtual:child': 'export default {render:()=>null}',
    'virtual:ant': 'export const message={success:msg=>globalThis.__desktopSettingsTest.successes.push(msg),error:msg=>globalThis.__desktopSettingsTest.errors.push(msg)}',
    'virtual:api': 'export const settingAPI=(action,payload)=>{const s=globalThis.__desktopSettingsTest;s.calls.push({action,payload:structuredClone(payload)});return s.handler(action,payload)}',
  }
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'desktop-settings-fixture', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }],
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  let app, vm
  try {
    const component = (await server.ssrLoadModule('/desktop-settings.js')).default
    const renderer = createRenderer({ createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {}, parentNode: () => null, nextSibling: () => null })
    app = renderer.createApp({ setup(props, context) { vm = component.setup(props, context); return () => h('div') } })
    const messages = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
    app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } }))
    app.mount({}); await flush()
    await run({ vm, state, listeners, unmount: () => { app.unmount(); app = null } })
  } finally { app?.unmount(); await server.close(); globalThis.window = previousWindow; delete globalThis.__desktopSettingsTest }
}

test('window preferences save immediately, survive reopening and reflect a choice remembered in the native dialog', async () => {
  await settings(async ({ vm, state, listeners }) => {
    assert.equal(vm.closeAction.value, 'ask')
    assert.equal(vm.trayAvailable.value, true)
    await vm.save('tray')
    assert.deepEqual(state.calls.at(-1), { action: 'update_window_setting', payload: { close_action: 'tray' } })
    assert.equal(vm.closeAction.value, 'tray')
    assert.equal(state.successes.length, 1)
    state.stored.close_action = 'exit'
    listeners.get('focus')(); await flush()
    assert.equal(vm.closeAction.value, 'exit', 'native remember choice is refreshed when focus returns')
    await vm.save('ask')
    assert.equal(state.stored.close_action, 'ask')
  })
})

test('failed saves keep the previous close policy and concurrent changes cannot submit twice', async () => {
  await settings(async ({ vm, state }) => {
    const pending = deferred()
    state.handler = () => pending.promise
    const saving = vm.save('tray')
    assert.equal(vm.saving.value, true)
    const count = state.calls.length
    await vm.save('exit')
    assert.equal(state.calls.length, count)
    pending.resolve({ status: 503 })
    await saving
    assert.equal(vm.closeAction.value, 'ask')
    assert.equal(vm.saving.value, false)
    assert.equal(state.errors.length, 1)
  })
})

test('window settings retry failed loads and reject stale or unmounted responses', async () => {
  await settings(async ({ vm, state, listeners, unmount }) => {
    state.handler = async () => { throw new Error('Synthetic read failure') }
    await vm.load()
    assert.equal(vm.failed.value, true)
    const old = deferred()
    state.handler = () => old.promise
    const loading = vm.load()
    state.handler = async () => ({ status: 200, data: { close_action: 'exit', tray_available: false } })
    await vm.load()
    old.resolve({ status: 200, data: { close_action: 'ask', tray_available: true } }); await loading
    assert.equal(vm.closeAction.value, 'exit')
    assert.equal(vm.trayAvailable.value, false)
    assert.equal(vm.failed.value, false)
    const late = deferred()
    state.handler = () => late.promise
    const request = vm.load()
    unmount()
    assert.equal(listeners.size, 0)
    late.resolve({ status: 200, data: { close_action: 'tray', tray_available: true } }); await request
    assert.equal(vm.closeAction.value, 'exit')
  })
})

test('minimize uses the desktop bridge, blocks duplicates and reports native failure', async () => {
  await settings(async ({ vm, state }) => {
    const pending = deferred()
    state.handler = () => pending.promise
    const minimizing = vm.minimize()
    const count = state.calls.length
    await vm.minimize()
    assert.equal(state.calls.length, count)
    assert.equal(state.calls.at(-1).action, 'minimize_to_tray')
    pending.resolve({ status: 503 }); await minimizing
    assert.equal(vm.minimizing.value, false)
    assert.equal(state.errors.length, 1)
    vm.trayAvailable.value = false
    await vm.minimize()
    assert.equal(state.calls.length, count, 'unavailable tray never hides the window')
  })
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick, reactive } from 'vue'
import { createI18n } from 'vue-i18n'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'
import { createServer } from 'vite'
import { previewSourceUrl, buildPreviewHtml } from '../src/utils/htmlPreview.js'

const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
const flush = async () => { for (let i = 0; i < 5; i++) await nextTick() }
const findAll = (node, type) => [ ...(node.type === type ? [node] : []), ...(node.children || []).flatMap(child => findAll(child, type)) ]

const createTestRenderer = () => createRenderer({ createElement: type => ({ type, children: [], props: {} }), createText: text => ({ text }), createComment: text => ({ text }),
      setText: (node, text) => { node.text = text }, setElementText: (node, text) => { node.text = text }, parentNode: node => node.parent,
      nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null, patchProp: (node, key, _old, value) => { node.props[key] = value },
      insert: (node, parent, anchor) => { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = parent; const index = anchor ? parent.children.indexOf(anchor) : -1; if (index < 0) parent.children.push(node); else parent.children.splice(index, 0, node) },
      remove: node => { if (node?.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1) } })

// This deliberately models only base-element operations; browser parsing is checked in the browser.
class PreviewParser {
  parseFromString(content) {
    const href = /<base href="([^"]*)"/.exec(content)?.[1]
    const base = { href, getAttribute() { return this.href }, setAttribute(_, value) { this.href = value } }
    return { querySelector: () => href === undefined ? null : base, createElement: () => base,
      head: { prepend() {} }, documentElement: { get outerHTML() { return `<html><head><base href="${base.href}"></head><body>${content}</body></html>` } } }
  }
}

test('HTML preview accepts only public HTTP URL syntax and resolves relative bases against the response URL', () => {
  for (const value of ['', '/relative', 'javascript:alert(1)', 'data:text/html,hi', 'file:///tmp/a', 'blob:https://example.com/id', 'https://user:pass@example.com/']) assert.equal(previewSourceUrl(value), '')
  assert.equal(previewSourceUrl('https://example.com/a?q=1'), 'https://example.com/a?q=1')
  assert.equal(previewSourceUrl('http://example.com'), 'http://example.com/')
  const previous = globalThis.DOMParser
  globalThis.DOMParser = PreviewParser
  try {
    assert.match(buildPreviewHtml('hello', 'https://example.com/final/page.html'), /base href="https:\/\/example.com\/final\/page.html"/)
    assert.match(buildPreviewHtml('<base href="../assets/">', 'https://example.com/final/page.html'), /base href="https:\/\/example.com\/assets\/"/)
    assert.match(buildPreviewHtml('<base href="javascript:alert(1)">', 'https://example.com/'), /base href="about:blank"/)
  } finally { globalThis.DOMParser = previous }
})

test('mounted HTML preview handles fetch races, iframe readiness, retries, fullscreen and cleanup', async () => {
  const filename = fileURLToPath(new URL('../src/components/HtmlPreview.vue', import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const compiled = compileScript(descriptor, { id: 'html-preview-test' })
  const script = compiled.content.replace('export default', 'const component =').replace("'ant-design-vue'", "'virtual:preview-theme'").replace("'@/icons'", "'virtual:preview-icons'")
  const template = compileTemplate({ source: descriptor.template.content, filename, id: 'html-preview-test', compilerOptions: { bindingMetadata: compiled.bindings } }).code.replace('export function render', 'function render')
  const moduleId = '/html-preview-mounted.js'
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'html-preview-test', resolveId: id => [moduleId, 'virtual:preview-theme', 'virtual:preview-icons'].includes(id) ? id : undefined,
      load: id => id === moduleId ? `${script}\n${template}\ncomponent.render = render; export default component`
        : id === 'virtual:preview-theme' ? 'import {ref} from "vue"; export const theme = {useToken:()=>({token:ref({})})}; export const message = {error: (...args)=>globalThis.__previewErrors.push(args)}'
          : id === 'virtual:preview-icons' ? 'export const FullScreenOne = {render:()=>null}; export const OffScreenOne = {render:()=>null}' : undefined }],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } }, server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  const saved = Object.fromEntries(['fetch', 'document', 'DOMParser', 'setTimeout', 'clearTimeout', '__previewErrors'].map(key => [key, globalThis[key]]))
  const oldCreate = URL.createObjectURL, oldRevoke = URL.revokeObjectURL
  const requests = [], blobs = [], revoked = [], timers = new Map(), listeners = new Map()
  let timerId = 0, exits = 0, app, c, mounted = false
  try {
    globalThis.fetch = (url, options) => { const request = { ...deferred(), url, options }; requests.push(request); return request.promise }
    globalThis.DOMParser = PreviewParser
    globalThis.__previewErrors = []
    globalThis.document = { fullscreenElement: null, addEventListener: (name, callback) => listeners.set(name, callback), removeEventListener: name => listeners.delete(name), exitFullscreen: async () => { exits++ } }
    URL.createObjectURL = blob => { blobs.push(blob); return `blob:preview-${blobs.length}` }
    URL.revokeObjectURL = url => revoked.push(url)
    const component = (await server.ssrLoadModule(moduleId)).default
    globalThis.setTimeout = (callback, delay) => { const id = ++timerId; timers.set(id, { callback, delay }); return id }
    globalThis.clearTimeout = id => timers.delete(id)
    const renderer = createTestRenderer()
    const props = reactive({ url: 'https://example.com/one.html' })
    const wrapped = { ...component, setup(p, ctx) { c = component.setup(p, ctx); return c } }
    app = renderer.createApp({ render: () => h(wrapped, props) })
    app.use(createI18n({ legacy: false, locale: 'en', messages: { en: JSON.parse(await readFile(new URL('../src/locales/en-US.json', import.meta.url), 'utf8')) } }))
    for (const name of ['ATooltip', 'AButton', 'ASpin']) app.component(name, { inheritAttrs: false, setup: (_, { attrs, slots }) => () => h(name, attrs, [slots.default?.(), slots.icon?.()]) })
    const root = { children: [] }
    app.mount(root); mounted = true
    assert.equal(requests[0].options.credentials, 'omit')
    assert.equal(requests[0].options.signal instanceof AbortSignal, true)
    assert.equal(findAll(root, 'ASpin').length, 1)
    assert.equal([...timers.values()][0].delay, 30000)
    requests[0].resolve({ ok: false }); await flush()
    assert.equal(c.failed.value, true)
    assert.equal(requests[0].options.signal.aborted, true)
    const retry = c.load()
    requests[1].resolve({ ok: true, url: 'https://example.com/final/page.html', text: async () => 'hello' }); await retry; await flush()
    let frame = findAll(root, 'iframe')[0]
    assert.equal(frame.props.sandbox, 'allow-scripts')
    assert.equal(frame.props.referrerpolicy, 'no-referrer')
    assert.equal(c.loading.value, true, 'fetch completion does not hide the loading state')
    assert.equal(findAll(root, 'ASpin').length, 1)
    assert.match(await blobs[0].text(), /https:\/\/example.com\/final\/page.html/)
    frame.props.onLoad({ target: {} }); assert.equal(c.loading.value, true)
    frame.props.onLoad({ target: c.frame.value }); await flush()
    assert.equal(c.loading.value, false); assert.equal(timers.size, 0)
    frame.props.onError({ target: c.frame.value }); await flush()
    assert.equal(c.failed.value, true); assert.deepEqual(revoked, ['blob:preview-1'])
    const staleFetch = c.load(); const staleRequest = requests.at(-1)
    props.url = 'https://example.com/two.html'; await flush()
    assert.equal(staleRequest.options.signal.aborted, true)
    staleRequest.resolve({ ok: true, text: async () => 'stale fetch' }); await staleFetch
    assert.equal(blobs.length, 1)
    const body = deferred(), bodyRequest = requests.at(-1)
    bodyRequest.resolve({ ok: true, text: () => body.promise }); await flush()
    const reload = c.load()
    assert.equal(bodyRequest.options.signal.aborted, true)
    body.resolve('stale body'); await flush()
    assert.equal(blobs.length, 1, 'same-URL retries also reject old body results')
    requests.at(-1).resolve({ ok: true, text: async () => 'current' }); await reload; await flush()
    assert.equal(c.frameUrl.value, 'blob:preview-2')
    props.url = 'https://example.com/three.html'; await flush()
    assert.ok(revoked.includes('blob:preview-2'))
    const timeoutRequest = requests.at(-1)
    ;[...timers.values()][0].callback(); await flush()
    assert.equal(timeoutRequest.options.signal.aborted, true); assert.equal(c.failed.value, true)
    timeoutRequest.resolve({ ok: true, text: async () => 'late timeout' }); await flush()
    assert.equal(blobs.length, 2)
    const interruptedLoad = c.load(), interruptedRequest = requests.at(-1)
    const pendingCount = requests.length
    props.pending = true; await flush()
    assert.equal(interruptedRequest.options.signal.aborted, true)
    assert.equal(requests.length, pendingCount, 'pending does not fetch the previous output URL')
    assert.equal(findAll(root, 'ASpin').length, 1)
    assert.equal(findAll(root, 'div').filter(node => node.props.role === 'status').length, 1)
    assert.equal(findAll(root, 'iframe').length, 0)
    assert.equal(timers.size, 0, 'workflow execution does not start the preview fetch timeout')
    interruptedRequest.resolve({ ok: true, text: async () => 'old execution' }); await interruptedLoad
    assert.equal(blobs.length, 2)
    props.url = ''; await flush()
    assert.equal(requests.length, pendingCount)
    assert.equal(findAll(root, 'section').length, 1, 'pending output without a URL remains visible')
    assert.equal(findAll(root, 'ASpin').length, 1)
    assert.equal(findAll(root, 'div').filter(node => node.props.role === 'status').length, 1)
    props.url = 'https://example.com/completed.html'; await flush()
    assert.equal(requests.length, pendingCount, 'new output also waits for execution completion')
    props.pending = false; await flush()
    assert.equal(requests.length, pendingCount + 1)
    assert.equal(requests.at(-1).url, props.url)
    requests.at(-1).resolve({ ok: false }); await flush()
    c.container.value.requestFullscreen = async () => { document.fullscreenElement = c.container.value }
    await c.toggleFullscreen(); listeners.get('fullscreenchange')()
    assert.equal(c.fullscreen.value, true)
    await c.toggleFullscreen(); assert.equal(exits, 1)
    document.fullscreenElement = null; listeners.get('fullscreenchange')()
    c.container.value.requestFullscreen = async () => { throw new Error('denied') }
    await c.toggleFullscreen(); assert.equal(globalThis.__previewErrors.length, 1)
    document.fullscreenElement = c.container.value; listeners.get('fullscreenchange')()
    document.exitFullscreen = async () => { throw new Error('denied') }
    await c.toggleFullscreen(); assert.equal(globalThis.__previewErrors.length, 2)
    const finalLoad = c.load()
    requests.at(-1).resolve({ ok: true, text: async () => 'final' }); await finalLoad; await flush()
    app.unmount(); mounted = false; await flush()
    assert.ok(revoked.includes('blob:preview-3')); assert.equal(listeners.size, 0); assert.equal(timers.size, 0)
  } finally {
    if (mounted) app.unmount()
    Object.assign(globalThis, saved)
    URL.createObjectURL = oldCreate; URL.revokeObjectURL = oldRevoke
    await server.close()
  }
})


test('record previews follow replaced history props without mutating saved UI arrays', async () => {
  const filename = fileURLToPath(new URL('../src/components/workspace/WorkflowRecordShow.vue', import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const compiled = compileScript(descriptor, { id: 'record-preview-test' })
  const script = compiled.content.replace('export default', 'const component =')
    .replace(/(['"])@\/components\/[^'"]+\1/g, "'virtual:record-child'")
  const template = compileTemplate({ source: descriptor.template.content, filename, id: 'record-preview-test', compilerOptions: { bindingMetadata: compiled.bindings } }).code.replace('export function render', 'function render')
  const workflow = (await readFile(new URL('../src/utils/workflow.js', import.meta.url), 'utf8')).replace("'ant-design-vue'", "'virtual:record-dependencies'").replace("'@/locales'", "'virtual:record-dependencies'")
  const util = (await readFile(new URL('../src/utils/util.js', import.meta.url), 'utf8')).replace('"@/stores/userSettings"', "'virtual:record-dependencies'")
  const moduleId = '/record-preview-mounted.js'
  const modules = {
    [moduleId]: `${script}\n${template}\ncomponent.render = render; export default component`,
    '@/utils/workflow': workflow, '@/utils/util': util,
    '@/icons': 'export const Dot = {render:()=>null}',
    'virtual:record-dependencies': 'export default {}; export const message = {}; export const useUserSettingsStore = ()=>({})',
    'virtual:record-child': 'import {h} from "vue"; export default {inheritAttrs:false, setup:(_, {attrs})=>()=>h("preview-child", attrs)}',
  }
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'record-preview-test', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }],
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  let app
  try {
    const component = (await server.ssrLoadModule(moduleId)).default
    const renderer = createTestRenderer()
    const history = url => ({ data: { nodes: [{ id: 'html', category: 'outputs', type: 'Html', data: { title: 'Saved HTML', template: { output: { value: url } } } }],
      ui: { inputFields: [], outputNodes: [{ id: 'obsolete', type: 'Html' }], triggerNodes: [] } } })
    const first = history('https://example.com/first.html'), second = history('https://example.com/second.html')
    const snapshots = JSON.stringify([first, second])
    const props = reactive({ workflowData: first })
    app = renderer.createApp({ render: () => h(component, props) })
    for (const name of ['ACol', 'ATypographyTitle']) app.component(name, { setup: (_, { slots }) => () => h(name, slots.default?.()) })
    const root = { children: [] }
    app.mount(root)
    assert.equal(findAll(root, 'preview-child')[0].props.url, 'https://example.com/first.html')
    assert.equal(findAll(root, 'preview-child')[0].props.title, 'Saved HTML')
    assert.equal(JSON.stringify([first, second]), snapshots, 'UI helper must receive a copy of the first record')
    props.workflowData = second; await flush()
    assert.equal(findAll(root, 'preview-child').length, 1)
    assert.equal(findAll(root, 'preview-child')[0].props.url, 'https://example.com/second.html')
    assert.equal(JSON.stringify([first, second]), snapshots, 'neither history record changes during recomputation')
  } finally { app?.unmount(); await server.close() }
})

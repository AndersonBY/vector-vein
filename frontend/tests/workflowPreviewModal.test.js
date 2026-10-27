import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick, reactive } from 'vue'
import { createI18n } from 'vue-i18n'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'
import { createServer } from 'vite'

const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
const flush = async () => { await nextTick(); await nextTick() }
const graph = label => ({ title: label, data: { nodes: [{ id: label, data: { title: label } }], edges: [] } })

test('preview opens without selecting, handles failures, and rejects stale loads after closing or switching workflows', async () => {
  const previous = globalThis.__previewRequest
  const requests = []
  globalThis.__previewRequest = (action, payload) => {
    const request = deferred()
    requests.push({ action, payload, ...request })
    return request.promise
  }
  const filename = fileURLToPath(new URL('../src/components/workspace/WorkflowPreviewModal.vue', import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const compiled = compileScript(descriptor, { id: 'preview-modal-test' })
  const script = compiled.content.replace('export default', 'const component =')
    .replace("'@/api/workflow'", "'virtual:preview-api'")
    .replace("'./CanvasPreview.vue'", "'virtual:preview-canvas'")
  const template = compileTemplate({ source: descriptor.template.content, filename, id: 'preview-modal-test',
    compilerOptions: { bindingMetadata: compiled.bindings } }).code.replace('export function render', 'function render')
  const moduleId = '/preview-modal-mounted.js'
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'preview-modal-test', resolveId: id => [moduleId, 'virtual:preview-api', 'virtual:preview-canvas'].includes(id) ? id : undefined,
      load: id => id === moduleId ? `${script}\n${template}\ncomponent.render = render; export default component`
        : id === 'virtual:preview-api' ? 'export const workflowAPI = (...args) => globalThis.__previewRequest(...args)'
          : id === 'virtual:preview-canvas' ? 'export default { render: () => null }' : undefined }],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  let app
  try {
    const component = (await server.ssrLoadModule(moduleId)).default
    const renderer = createRenderer({
      createElement: type => ({ type, children: [], props: {} }), createText: text => ({ text }), createComment: text => ({ text }),
      setText: (node, text) => { node.text = text }, setElementText: (node, text) => { node.text = text },
      parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
      patchProp: (node, key, _old, value) => { node.props[key] = value },
      insert: (node, parent, anchor) => {
        if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
        node.parent = parent
        const index = anchor ? parent.children.indexOf(anchor) : -1
        if (index < 0) parent.children.push(node)
        else parent.children.splice(index, 0, node)
      },
      remove: node => { if (node?.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1) },
    })
    let c
    const props = reactive({ workflowId: 'first', workflow: null, title: 'First' })
    const wrapped = { ...component, setup(p, ctx) { c = component.setup(p, ctx); return c } }
    app = renderer.createApp({ render: () => h(wrapped, { ...props }) })
    const messages = JSON.parse(await readFile(new URL('../src/locales/en-US.json', import.meta.url), 'utf8'))
    app.use(createI18n({ legacy: false, locale: 'en', messages: { en: messages } }))
    for (const name of ['ATooltip', 'AAlert', 'ASkeleton']) app.component(name, { setup: (_, { slots }) => () => h('div', slots.default?.()) })
    app.component('AButton', { inheritAttrs: false, setup: (_, { attrs, slots }) => () => h('button', attrs, slots.icon?.()) })
    app.component('AModal', { props: ['open', 'transitionName'], setup: (p, { slots }) => {
      assert.equal(p.transitionName, '')
      return () => p.open ? h('div', slots.default?.()) : null
    } })
    const root = { children: [] }
    app.mount(root)
    assert.equal(requests.length, 0)
    const findButton = node => node.type === 'button' ? node : node.children?.map(findButton).find(Boolean)
    let stopped = 0
    findButton(root).props.onClick({ stopPropagation() { stopped++ } })
    assert.equal(stopped, 1)
    assert.equal(c.open.value, true)
    assert.equal(c.loading.value, true)
    assert.deepEqual(requests[0].payload, { wid: 'first' })
    c.open.value = false
    c.openPreview()
    requests[0].resolve({ status: 200, data: graph('stale') })
    await flush()
    assert.equal(c.definition.value, null)
    assert.equal(c.loading.value, true)
    requests[1].resolve({ status: 200, data: graph('current') })
    await flush()
    assert.equal(c.definition.value.nodes[0].id, 'current')
    assert.equal(c.loading.value, false)
    props.workflowId = 'second'
    await flush()
    assert.equal(c.definition.value, null)
    requests[2].resolve({ status: 403, data: graph('must-not-show') })
    await flush()
    assert.equal(c.failed.value, true)
    assert.equal(c.definition.value, null)
    const retry = c.loadPreview()
    requests[3].resolve({ status: 200, data: graph('retried') })
    await retry
    assert.equal(c.failed.value, false)
    assert.equal(c.definition.value.nodes[0].id, 'retried')
    const next = c.loadPreview()
    props.workflowId = 'third'
    await flush()
    requests[4].resolve({ status: 500 })
    await next
    assert.equal(c.failed.value, false)
    requests[5].resolve({ status: 200, data: graph('third') })
    await flush()
    assert.equal(c.definition.value.nodes[0].id, 'third')
    const template = graph('template')
    const before = JSON.stringify(template)
    props.workflow = template
    await flush()
    assert.equal(requests.length, 6)
    assert.equal(c.definition.value.nodes[0].id, 'template')
    assert.equal(JSON.stringify(template), before)
    props.workflow = null
    await flush()
    app.unmount()
    requests[6].resolve({ status: 200, data: graph('unmounted') })
    await flush()
    assert.equal(c.definition.value, null)
  } finally { app?.unmount(); await server.close(); globalThis.__previewRequest = previous }
})

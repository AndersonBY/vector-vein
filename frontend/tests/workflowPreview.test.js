import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createI18n } from 'vue-i18n'
import { ConfigProvider, theme } from 'ant-design-vue'
import { createServer } from 'vite'
import vue from '@vitejs/plugin-vue'
import { getWorkflowPreview } from '../src/utils/workflowPreview.js'

const messages = {
  'components.nodes.tools.HttpRequest.title': 'HTTP request',
  'components.nodes.tools.HttpRequest.url': 'URL',
  'components.nodes.tools.HttpRequest.response_body': 'Response text',
}
const t = key => messages[key]
const te = key => Object.hasOwn(messages, key)
const fixture = () => ({
  nodes: [
    { id: 'request', type: 'HttpRequest', category: 'tools', position: { x: -20, y: 30 }, data: { template: {
      url: { id: 'url-id', name: 'url', display_name: 'url', value: 'private URL' },
      response_body: { name: 'response_body', is_output: true, value: 'private response' },
    } } },
    { id: 'next', type: 'CustomUnknown', category: 'custom', position: { x: 400, y: 50 }, ignored: true,
      data: { title: 'Custom title', template: { incoming: { name: 'incoming', display_name: 'Friendly input', value: 'secret' } } } },
  ],
  edges: [
    { id: 'output', source: 'request', sourceHandle: 'response_body', target: 'next', targetHandle: 'incoming' },
    { id: 'passthrough', source: 'request', sourceHandle: 'url-id', target: 'next', targetHandle: 'other' },
    { id: 'input', source: 'next', sourceHandle: 'result', target: 'request', targetHandle: 'url-id', ignored: true },
  ],
})
function freeze(value) {
  if (value && typeof value === 'object') { Object.freeze(value); Object.values(value).forEach(freeze) }
  return value
}

test('preview projects positions, custom and translated labels, ignored nodes, and passthrough handles', () => {
  const source = fixture()
  const { nodes, edges } = getWorkflowPreview(source, t, te)
  assert.equal(nodes[0].data.title, 'HTTP request')
  assert.equal(nodes[1].data.title, 'Custom title')
  assert.deepEqual(nodes[0].position, { x: -20, y: 30 })
  assert.equal(nodes[1].data.ignored, true)
  assert.deepEqual(nodes[0].data.inputs, [{ id: 'url-id', label: 'URL' }])
  assert.deepEqual(nodes[0].data.outputs, [{ id: 'response_body', label: 'Response text' }, { id: 'url-id', label: 'URL' }])
  assert.equal(nodes[1].data.inputs[0].label, 'Friendly input')
  assert.equal(nodes[1].data.inputs[1].label, 'other')
  assert.deepEqual(edges.map(edge => [edge.sourceHandle, edge.targetHandle]), [['response_body', 'incoming'], ['url-id', 'other'], ['result', 'url-id']])
  assert.ok(edges.every(edge => edge.style.opacity === 0.4))
  assert.ok(edges.every(edge => edge.style.stroke === 'var(--preview-edge, #666)'
    && edge.markerEnd.color === 'var(--preview-edge, #666)'))
  assert.ok(nodes.every(node => node.type === 'preview' && !node.draggable && !node.connectable && !node.selectable && !node.focusable))
})

test('canvas data never shares or exposes editable template values or caller objects', () => {
  const source = freeze(fixture())
  const before = JSON.stringify(source)
  const first = getWorkflowPreview(source, t, te)
  const second = getWorkflowPreview(source, t, te)
  first.nodes[0].position.x = 999
  first.nodes[0].data.inputs[0].label = 'changed'
  first.edges[0].style.opacity = 1
  first.edges[0].markerEnd.type = 'changed'
  assert.equal(JSON.stringify(source), before)
  assert.equal(second.nodes[0].position.x, -20)
  assert.equal(second.nodes[0].data.inputs[0].label, 'URL')
  assert.equal(second.edges[0].style.opacity, 0.4)
  assert.equal(second.edges[0].markerEnd.type, 'arrowclosed')
  assert.ok(!JSON.stringify(second).includes('private'))
  assert.ok(!JSON.stringify(second).includes('secret'))
  assert.ok(!('template' in second.nodes[0].data))
})

test('preview tolerates empty, unknown, missing-template and invalid graph data', () => {
  for (const source of [null, undefined, {}, { nodes: {}, edges: {} }]) assert.deepEqual(getWorkflowPreview(source), { nodes: [], edges: [] })
  const preview = getWorkflowPreview({ nodes: [null, {}, { id: 12 }, { id: 'a', type: 'Unknown', position: { x: Infinity } },
    { id: 'a', type: 'Duplicate' }, { id: 'b' }], edges: [null, {}, { source: 'missing', target: 'a' },
    { source: 'a', target: 'b', sourceHandle: 4 },
    { id: 'same', source: 'a', target: 'b' }, { id: 'same', source: 'a', target: 'b', sourceHandle: 'not-in-template' }] })
  assert.equal(preview.nodes.length, 2)
  assert.equal(preview.nodes[0].data.title, 'Unknown')
  assert.equal(preview.nodes[1].data.title, 'b')
  assert.deepEqual(preview.nodes[0].position, { x: 0, y: 0 })
  assert.equal(preview.edges.length, 2)
  assert.equal(new Set(preview.edges.map(edge => edge.id)).size, 2)
  assert.deepEqual(preview.nodes[0].data.outputs, [{ id: null, label: '—' }, { id: 'not-in-template', label: 'not-in-template' }])
  assert.deepEqual(preview.nodes[1].data.inputs, [{ id: null, label: '—' }])
})

test('preview title falls back to task localization while port aliases resolve to template names', () => {
  const preview = getWorkflowPreview({ nodes: [
    { id: 'a', data: { task_name: 'tools.http_request', template: { custom: { id: 'field-id', name: 'field-name', display_name: 'User port' } } } },
    { id: 'b', type: 'Unknown' },
  ], edges: [{ source: 'a', sourceHandle: 'field-name', target: 'b', targetHandle: 'missing' },
    { source: 'a', sourceHandle: 'field-id', target: 'b', targetHandle: 'missing' }] }, t, te)
  assert.equal(preview.nodes[0].data.title, 'HTTP request')
  assert.deepEqual(preview.nodes[0].data.outputs.map(port => port.label), ['User port', 'User port'])
  assert.equal(preview.nodes[1].data.inputs.length, 1)
})

test('real preview component creates separate VueFlow stores and renders a safe empty state', async () => {
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)), plugins: [vue()],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  try {
    const component = (await server.ssrLoadModule('/src/components/workspace/CanvasPreview.vue')).default
    const controllers = []
    const wrapped = { ...component, setup(props, ctx) { const c = component.setup(props, ctx); controllers.push(c); return c } }
    const app = createSSRApp({ render: () => h('div', [h(wrapped, { workflow: fixture() }),
      h(ConfigProvider, { theme: { algorithm: theme.darkAlgorithm } }, { default: () => h(wrapped, { workflow: {} }) }),
    ]) })
    app.use(createI18n({ legacy: false, locale: 'en', messages: { en: { workspace: { canvasPreview: {
      empty: 'No workflow nodes', ignored: 'Ignored', zoom_in: 'Zoom in', zoom_out: 'Zoom out', fit_view: 'Fit view',
    } } } } }))
    app.component('AButton', { setup: (props, { slots }) => () => h('button', slots.icon?.()) })
    const html = await renderToString(app)
    assert.equal(controllers.length, 2)
    assert.notEqual(controllers[0].flowId, controllers[1].flowId)
    assert.match(controllers[0].flowId, /^workflow-preview-/)
    assert.match(html, /No workflow nodes/)
    assert.ok(!html.includes('private URL'))
    assert.match(html, /--preview-background:/)
    assert.match(html, /--preview-edge:/)
    for (const c of controllers) {
      for (const name of ['background', 'text', 'border', 'edge', 'primary']) {
        assert.match(c.canvasStyle.value[`--preview-${name}`], /^(#|rgba?\()/, name)
      }
      assert.equal(c.canvasStyle.value['--preview-background'], c.token.value.colorBgContainer)
      assert.equal(c.canvasStyle.value['--preview-edge'], c.token.value.colorTextSecondary)
    }
    assert.notEqual(controllers[0].canvasStyle.value['--preview-background'], controllers[1].canvasStyle.value['--preview-background'])
    assert.notEqual(controllers[0].canvasStyle.value['--preview-edge'], controllers[1].canvasStyle.value['--preview-edge'])
    const { useVueFlow } = await server.ssrLoadModule('@vue-flow/core')
    const first = useVueFlow(controllers[0].flowId)
    const second = useVueFlow(controllers[1].flowId)
    assert.notEqual(first, second)
    assert.equal(first.id, controllers[0].flowId)
    assert.equal(second.id, controllers[1].flowId)
    const source = await readFile(new URL('../src/components/workspace/CanvasPreview.vue', import.meta.url), 'utf8')
    for (const option of ['nodes-draggable', 'nodes-connectable', 'elements-selectable', 'edges-updatable', 'nodes-focusable', 'edges-focusable']) {
      assert.ok(source.includes(`:${option}="false"`), option)
    }
    assert.ok(source.includes(':delete-key-code="null"'))
    assert.ok(source.includes(':selection-key-code="false"'))
    assert.match(source, /\.preview-node\s*\{[^}]*background: var\(--preview-background, #fff\)/)
    assert.match(source, /\.preview-controls :deep\(\.ant-btn\)\s*\{[^}]*background: var\(--preview-background, #fff\)/)
    assert.ok(!source.includes('var(--component-background)'))
    assert.ok(!source.includes('var(--site-light-text-color)'))
    const otherViewport = { ...second.viewport.value }
    first.viewport.value = { x: 123, y: 456, zoom: 0.5 }
    assert.deepEqual(second.viewport.value, otherViewport)
    first.$destroy()
    second.$destroy()
  } finally { await server.close() }
})

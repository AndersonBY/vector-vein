import assert from 'node:assert/strict'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { readFile } from 'node:fs/promises'
import { createRenderer, h, nextTick, reactive } from 'vue'
import { createI18n } from 'vue-i18n'
import { createServer } from 'vite'
import vue from '@vitejs/plugin-vue'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'
import { httpValueRows, parseHttpValue, serializeHttpRows, validateHttpRequestFields, findHttpRequestError } from '../src/components/nodes/tools/_httpRequestShared.js'
import { createTemplateData } from '../src/components/nodes/tools/HttpRequest.js'

test('HTTP row roundtrips retain scalar types, strings, list values and special keys', () => {
  const source = '{"zero":0,"false":false,"null":null,"list":[0,false,null,""],"str":"0","__proto__":"safe"}'
  const rows = httpValueRows(source, 'query').rows
  assert.equal(rows.find(row => row.key === 'str').type, 'text')
  assert.deepEqual(JSON.parse(serializeHttpRows(rows)), JSON.parse(source))
  assert.equal(httpValueRows('{"zero":0,"false":false,"null":null}', 'form').rows.length, 3)
  for (const value of [0, false, null, [], {}, '"hello"']) assert.equal(parseHttpValue(value, 'json').error, undefined)
})

test('HTTP validation rejects drafts without collapsing or coercing their entries', () => {
  for (const [source, kind, error] of [
    ['{"a":1,"a":2}', 'query', 'duplicate_key'],
    ['{"a\\u0062":1,"ab":2}', 'query', 'duplicate_key'],
    ['{"Accept":"a","accept":"b"}', 'headers', 'duplicate_key'],
    ['{"a":"line\\nfeed"}', 'headers', 'invalid_header'],
    ['{"bad key":"x"}', 'headers', 'invalid_header'],
    ['{"a":0}', 'headers', 'invalid_header'],
    ['{"":1}', 'query', 'empty_key'],
    ['{"a":{}}', 'query', 'query_value'],
    ['{"a":[{}]}', 'query', 'query_value'],
    ['{"a":[]}', 'form', 'form_value'],
    ['{"a":1e999}', 'query', 'query_value'],
    ['[1]', 'form', 'object_required'],
    ['{', 'query', 'invalid_json'],
  ]) assert.equal(parseHttpValue(source, kind).error, error, source)
  const rows = [{ key: 'same', type: 'text', value: 'first' }, { key: 'same', type: 'json', value: 'bad draft' }]
  const source = serializeHttpRows(rows)
  assert.ok(source.includes('first'))
  assert.ok(source.includes('bad draft'))
  assert.equal(parseHttpValue(source, 'query').error, 'invalid_json')
  assert.equal(parseHttpValue('{"nested": "a:b,{}[]\\\"", "other":0}', 'query').error, undefined)
  const fields = createTemplateData().template
  fields.headers.value = '{'
  fields.body_type.value = 'form'
  fields.body.value = '{"a":[]}'
  assert.deepEqual(validateHttpRequestFields(fields), [{ field: 'headers', error: 'invalid_json' }, { field: 'body', error: 'form_value' }])
  assert.deepEqual(validateHttpRequestFields(fields, ['headers', 'body_type']), [])
})

// A tiny Vue host mounts the actual SFC without a browser or a test-only DOM dependency.
function mount(component, props, messages) {
  const renderer = createRenderer({
    createElement: type => ({ type, children: [] }),
    createText: text => ({ text }), createComment: text => ({ text }),
    setText: (node, text) => { node.text = text }, setElementText: (node, text) => { node.text = text },
    parentNode: node => node.parent,
    nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
    patchProp: () => {},
    insert: (node, parent, anchor) => {
      if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
      node.parent = parent
      const index = anchor ? parent.children.indexOf(anchor) : -1
      if (index < 0) parent.children.push(node)
      else parent.children.splice(index, 0, node)
    },
    remove: node => { const i = node?.parent?.children.indexOf(node); if (i >= 0) node.parent.children.splice(i, 1) },
  })
  let controller
  const wrapped = { ...component, setup(p, ctx) { controller = component.setup(p, ctx); return controller } }
  const app = renderer.createApp({ setup: () => () => h(wrapped, { ...props, 'onUpdate:modelValue': value => { props.modelValue = value } }) })
  app.use(createI18n({ legacy: false, locale: 'en', messages: { en: messages } }))
  for (const name of ['AFlex', 'ATypographyText', 'ARadioGroup', 'AInput', 'ASelect', 'AButton', 'ATextarea']) {
    app.component(name, { setup: (p, { slots }) => () => h('div', slots.default?.()) })
  }
  app.mount({ children: [] })
  return { controller, app }
}

test('mounted HTTP editor preserves invalid drafts, synchronizes history and external values, and switches modes safely', async () => {
  const filename = fileURLToPath(new URL('../src/components/nodes/tools/_HttpRequestKeyValueEditor.vue', import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const compiled = compileScript(descriptor, { id: 'http-editor-test' })
  const script = compiled.content.replace('export default', 'const component =').replace("'./_httpRequestShared.js'", "'@/components/nodes/tools/_httpRequestShared.js'")
  const template = compileTemplate({ source: descriptor.template.content, filename, id: 'http-editor-test',
    compilerOptions: { bindingMetadata: compiled.bindings } }).code.replace('export function render', 'function render')
  const testId = '/src/components/nodes/tools/http-editor-mounted-test.js'
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)), plugins: [vue(), {
      name: 'http-editor-mounted-test',
      resolveId: id => [testId, 'virtual:http-editor-icons'].includes(id) ? id : undefined,
      load: id => id === testId ? `${script}\n${template}\ncomponent.render = render; export default component`
        : id === 'virtual:http-editor-icons' ? 'export const AddOne = { render: () => null }; export const ReduceOne = AddOne' : undefined,
    }],
    resolve: { alias: [{ find: '@/icons', replacement: 'virtual:http-editor-icons' },
      { find: '@', replacement: fileURLToPath(new URL('../src', import.meta.url)) }] },
    server: { middlewareMode: true, hmr: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  try {
    const component = (await server.ssrLoadModule(testId)).default
    const messages = JSON.parse(await readFile(new URL('../src/locales/en-US.json', import.meta.url), 'utf8'))
    const props = reactive({ modelValue: '{"n":0,"f":false,"z":null}', kind: 'query', disabled: false })
    const { controller: c, app } = mount(component, props, messages)
    assert.equal(c.rows.value.length, 3)
    c.addRow()
    await nextTick()
    assert.equal(c.error.value, 'empty_key')
    assert.equal(c.rows.value.length, 4)
    Object.assign(c.rows.value[3], { key: 'n', value: 'draft', type: 'text' })
    c.updateRows()
    await nextTick()
    assert.equal(c.error.value, 'duplicate_key')
    assert.equal(c.rows.value.length, 4)
    Object.assign(c.rows.value[3], { key: 'new', value: 'unfinished JSON', type: 'json' })
    c.updateRows()
    await nextTick()
    assert.equal(c.error.value, 'invalid_json')
    assert.ok(props.modelValue.includes('unfinished JSON'))
    assert.equal(c.rows.value[3].type, 'json')
    const invalidDraft = props.modelValue
    c.switchMode('json')
    assert.equal(c.source.value, invalidDraft)
    c.switchMode('rows')
    assert.equal(c.mode.value, 'json')
    c.publish('{')
    await nextTick()
    assert.equal(props.modelValue, '{')
    assert.equal(c.error.value, 'invalid_json')
    props.modelValue = '{"external":false}'
    await nextTick()
    c.switchMode('rows')
    assert.equal(c.rows.value[0].value, 'false')
    assert.equal(c.rows.value[0].type, 'json')
    // Undo can return to an earlier emitted value after an external replacement.
    props.modelValue = '{'
    await nextTick()
    assert.equal(c.source.value, '{')
    assert.equal(c.mode.value, 'json')
    props.modelValue = { oldWorkflow: 0 }
    await nextTick()
    c.switchMode('rows')
    assert.equal(c.rows.value[0].key, 'oldWorkflow')
    props.kind = 'form'
    await nextTick()
    assert.equal(props.modelValue.oldWorkflow, 0)
    props.disabled = true
    await nextTick()
    assert.equal(c.error.value, '')
    props.disabled = false
    props.kind = 'json'
    props.modelValue = false
    await nextTick()
    assert.equal(c.source.value, 'false')
    assert.equal(props.modelValue, false)
    props.modelValue = null
    await nextTick()
    assert.equal(c.source.value, 'null')
    assert.equal(c.error.value, undefined)
    app.unmount()
  } finally { await server.close() }
})

test('workflow HTTP preflight honors connected handles and ignored nodes, including old templates', () => {
  const fields = createTemplateData().template
  const node = { id: 'http', type: 'HttpRequest', data: { template: fields } }
  const source = { id: 'source' }
  const data = { nodes: [source, node], edges: [] }
  fields.headers.value = '{'
  assert.equal(findHttpRequestError(data).field, 'headers')
  for (const handle of ['headers', 'custom-id', 'custom-name']) {
    fields.headers.id = 'custom-id'
    fields.headers.name = 'custom-name'
    data.edges = [{ source: source.id, target: node.id, targetHandle: handle }]
    assert.equal(findHttpRequestError(data), null)
    source.ignored = true
    assert.equal(findHttpRequestError(data).field, 'headers')
    source.ignored = false
    data.edges[0].ignored = true
    assert.equal(findHttpRequestError(data).field, 'headers')
  }
  node.ignored = true
  assert.equal(findHttpRequestError(data), null)
  node.ignored = false
  delete fields.headers
  delete fields.query_params
  assert.equal(findHttpRequestError(data), null)
  fields.body_type.value = 'json'
  for (const value of [0, false, null, '{}', '[]', '"hello"', '{"a":1,"a":2}']) {
    fields.body.value = value
    assert.equal(findHttpRequestError(data), null)
  }
  fields.body.value = '{'
  assert.equal(findHttpRequestError(data).field, 'body')
  data.edges = [{ source: source.id, target: node.id, targetHandle: 'body' }]
  assert.equal(findHttpRequestError(data), null)
  data.edges[0].targetHandle = 'body_type'
  assert.equal(findHttpRequestError(data), null)
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { effectScope, reactive, createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createI18n } from 'vue-i18n'
import { createServer } from 'vite'
import vue from '@vitejs/plugin-vue'
import { useModelEndpointTest } from '../src/utils/modelEndpointTest.js'

function fixture(request) {
  const input = reactive({ active: true, backend: 'local', modelId: 'draft-model', message: 'Hi!',
    endpoint: { id: 'draft-endpoint', api_base: 'http://127.0.0.1:8080/v1', api_key: 'test-key',
      endpoint_type: 'openai', credentials: '{"project_id":"test-project"}', region: 'test-region', rpm: 7 } })
  const scope = effectScope()
  const controller = scope.run(() => useModelEndpointTest(() => input, request, key => key))
  return { input, scope, ...controller }
}

test('test sends the complete current draft with selected backend/model/message and never mutates it', async () => {
  let received
  const f = fixture(async (action, payload) => {
    received = { action, payload }
    return { status: 200, data: { content: 'Hello', reasoning_content: 'Reasoning' } }
  })
  try {
    f.input.backend = 'anthropic'
    f.input.modelId = 'override-model'
    f.input.message = 'Draft message'
    const before = JSON.stringify(f.input)
    await f.submit()
    assert.deepEqual(received, { action: 'test_model_endpoint', payload: {
      backend: 'anthropic', model_id: 'override-model', message: 'Draft message',
      endpoint: { ...JSON.parse(before).endpoint, credentials: { project_id: 'test-project' } },
    } })
    received.payload.endpoint.credentials.project_id = 'changed'
    assert.equal(JSON.stringify(f.input), before)
    assert.equal(f.state.content, 'Hello')
    assert.equal(f.state.reasoningContent, 'Reasoning')
    assert.equal(f.state.loading, false)
  } finally { f.scope.stop() }
})

test('blank model/message, missing endpoints and malformed credentials do not call the API', async () => {
  let calls = 0
  for (const change of [
    input => { input.modelId = '  ' }, input => { input.message = '\n ' },
    input => { input.endpoint = null }, input => { input.endpoint.credentials = 'invalid-private-text' },
  ]) {
    const f = fixture(async () => { calls += 1 })
    try {
      change(f.input)
      await f.submit()
      assert.ok(f.state.error)
      assert.doesNotMatch(f.state.error, /invalid-private-text/)
      assert.equal(f.state.loading, false)
    } finally { f.scope.stop() }
  }
  assert.equal(calls, 0)
})

test('late responses are ignored after endpoint, model, message, backend edits, close or unmount', async () => {
  for (const change of [
    f => { f.input.endpoint = { ...f.input.endpoint, id: 'other' } },
    f => { f.input.endpoint.api_key = 'new-key' },
    f => { f.input.modelId = 'other-model' }, f => { f.input.message = 'other-message' },
    f => { f.input.backend = 'openai' }, f => { f.input.active = false }, f => f.scope.stop(),
  ]) {
    let resolve
    const f = fixture(() => new Promise(done => { resolve = done }))
    try {
      const pending = f.submit()
      assert.equal(f.state.loading, true)
      change(f)
      assert.equal(f.state.loading, false)
      resolve({ status: 200, data: { content: 'stale' } })
      await pending
      assert.equal(f.state.content, '')
      assert.equal(f.state.completed, false)
    } finally { f.scope.stop() }
  }
})

test('duplicate requests are suppressed, exceptions clear loading, and old results clear on edits', async () => {
  let reject
  let calls = 0
  const f = fixture(() => { calls += 1; return new Promise((resolve, fail) => { reject = fail }) })
  try {
    const pending = f.submit()
    await f.submit()
    assert.equal(calls, 1)
    reject(new Error('private provider request with credentials'))
    await pending
    assert.equal(f.state.loading, false)
    assert.equal(f.state.error, 'settings.model_test_failed')
    f.input.modelId = 'changed'
    assert.equal(f.state.error, '')
  } finally { f.scope.stop() }

  const success = fixture(async () => ({ status: 200, data: { content: 'old' } }))
  try {
    success.input.endpoint.credentials = { project_id: 'object-supported' }
    await success.submit()
    success.input.message = 'new'
    assert.equal(success.state.content, '')
    assert.equal(success.state.completed, false)
  } finally { success.scope.stop() }
})

test('a superseded request cannot clear a newer request spinner or result; API failures show safe messages', async () => {
  const resolves = []
  const f = fixture(() => new Promise(done => { resolves.push(done) }))
  try {
    const oldRequest = f.submit()
    f.input.modelId = 'new'
    const newRequest = f.submit()
    resolves[0]({ status: 502, msg: 'Old failure' })
    await oldRequest
    assert.equal(f.state.loading, true)
    assert.equal(f.state.error, '')
    resolves[1]({ status: 502, msg: 'Endpoint returned 401' })
    await newRequest
    assert.equal(f.state.loading, false)
    assert.equal(f.state.error, 'Endpoint returned 401')
  } finally { f.scope.stop() }
})

test('model replies, reasoning and errors render as escaped plain text in the real component', async () => {
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)), plugins: [vue()],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  try {
    const { default: component } = await server.ssrLoadModule('/src/components/settings/ModelEndpointTest.vue')
    const messages = JSON.parse(await readFile(new URL('../src/locales/en-US.json', import.meta.url), 'utf8'))
    const setup = component.setup
    const app = createSSRApp({ ...component, setup(props, context) {
      const bindings = setup(props, context)
      Object.assign(bindings.state, { completed: true, content: '<script>reply</script>',
        reasoningContent: '<b>reasoning</b>', error: '<img src=x onerror=alert(1)>' })
      return bindings
    } })
    app.use(createI18n({ legacy: false, locale: 'en', messages: { en: messages } }))
    for (const name of ['ADivider', 'AForm', 'AFormItem', 'ATypographyTitle', 'ATypographyParagraph', 'ATypographyText', 'AButton', 'ATextarea', 'ASelect', 'AInput']) {
      app.component(name, { setup: (props, { slots }) => () => h('div', slots.default?.()) })
    }
    const html = await renderToString(app)
    assert.match(html, /&lt;script&gt;reply&lt;\/script&gt;/)
    assert.match(html, /&lt;b&gt;reasoning&lt;\/b&gt;/)
    assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/)
    assert.doesNotMatch(html, /<script>|<b>reasoning|<img/)
  } finally { await server.close() }
})

test('actual settings components send unsaved endpoint drafts and remote/custom model mapping selections', async () => {
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)), plugins: [vue()],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  const originalWindow = globalThis.window
  let component, originalSetup
  try {
    component = (await server.ssrLoadModule('/src/components/settings/ModelEndpointTest.vue')).default
    originalSetup = component.setup
    const payloads = []
    globalThis.window = { pywebview: { api: { setting__test_model_endpoint: async payload => {
      payloads.push(payload)
      return { status: 200, data: { content: 'integration reply' } }
    } } } }
    component.setup = async (props, context) => {
      const bindings = originalSetup(props, context)
      if (props.editableModel) bindings.modelId.value = 'unsaved-model'
      await bindings.submit()
      return bindings
    }
    const messages = JSON.parse(await readFile(new URL('../src/locales/en-US.json', import.meta.url), 'utf8'))
    const render = async (root, props, prepare) => {
      const app = createSSRApp({ ...root, setup(props, context) {
        const bindings = root.setup(props, context)
        prepare(bindings)
        return bindings
      } }, props)
      app.use(createI18n({ legacy: false, locale: 'en', messages: { en: messages } }))
      for (const name of ['ADivider', 'AForm', 'AFormItem', 'ATypographyTitle', 'ATypographyParagraph', 'ATypographyText',
        'AButton', 'ATextarea', 'ASelect', 'AInput', 'AModal', 'AFlex', 'AList', 'AListItem', 'ATooltip',
        'ASwitch', 'AInputNumber', 'ARow', 'ACol', 'ATag', 'AInputPassword', 'ATable', 'ASpace', 'APopover']) {
        app.component(name, { setup: (props, { slots }) => () => h('div', slots.default?.()) })
      }
      return renderToString(app)
    }
    const endpoint = { id: 'selected', api_base: 'http://127.0.0.1:8080/v1', api_key: 'test-key', credentials: {} }
    const mapping = (await server.ssrLoadModule('/src/components/settings/LLMStandardSettings.vue')).default
    for (const [backend, modelEndpoint, expectedModel] of [
      ['openai', 'selected', 'base-model'], ['anthropic', { endpoint_id: 'selected', model_id: 'override-model' }, 'override-model'],
      [undefined, 'selected', 'base-model'],
    ]) {
      const settings = { models: { key: { id: 'base-model', endpoints: [modelEndpoint] } } }
      const before = JSON.stringify(settings)
      const html = await render(mapping, { modelValue: settings, endpoints: [endpoint], backend }, bindings => {
        bindings.editModel(settings.models.key, 'key')
        bindings.editEndpoint(0)
      })
      assert.match(html, /integration reply/)
      assert.deepEqual(payloads.at(-1), { backend: backend || 'local', endpoint, model_id: expectedModel, message: 'Hi' })
      assert.equal(JSON.stringify(settings), before)
    }
    const endpointSettings = (await server.ssrLoadModule('/src/components/settings/EndpointSettings.vue')).default
    const endpoints = []
    await render(endpointSettings, { endpoints, localModels: { models: {} }, modelFamilyMap: {} }, bindings => {
      bindings.resetForm()
      Object.assign(bindings.endpointForm, endpoint, { id: 'unsaved-endpoint', api_base: 'http://127.0.0.1:9999/v1',
        credentials: '{"project_id":"unsaved-project"}' })
    })
    assert.equal(payloads.at(-1).model_id, 'unsaved-model')
    assert.equal(payloads.at(-1).endpoint.id, 'unsaved-endpoint')
    assert.equal(payloads.at(-1).endpoint.api_base, 'http://127.0.0.1:9999/v1')
    assert.deepEqual(payloads.at(-1).endpoint.credentials, { project_id: 'unsaved-project' })
    assert.equal(endpoints.length, 0)
  } finally {
    if (component) component.setup = originalSetup
    if (originalWindow === undefined) delete globalThis.window
    else globalThis.window = originalWindow
    await server.close()
  }
})

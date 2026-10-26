import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createI18n } from 'vue-i18n'
import { createServer } from 'vite'
import vue from '@vitejs/plugin-vue'

test('endpoint editor stages replacement, priorities and stable ordering until model confirmation', async () => {
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)), plugins: [vue()],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  try {
    const component = (await server.ssrLoadModule('/src/components/settings/LLMStandardSettings.vue')).default
    const messages = JSON.parse(await readFile(new URL('../src/locales/en-US.json', import.meta.url), 'utf8'))
    const settings = { models: { key: { id: 'base-model', custom_model_option: 'keep', endpoints: [
      { endpoint_id: 'later', priority: 3 },
      'legacy',
      { endpoint_id: 'editable', model_id: 'old', enabled: false, capabilities: { tools: true }, rpm: 9 },
    ] } } }
    const before = JSON.stringify(settings)
    const endpoints = ['later', 'legacy', 'editable', 'new'].map(id => ({ id }))
    let controller
    const app = createSSRApp({ ...component, setup(props, context) {
      const c = component.setup(props, context)
      controller = c
      c.editModel(settings.models.key, 'key')
      assert.deepEqual(c.modelForm.endpoints.map(e => typeof e === 'string' ? e : e.endpoint_id), ['legacy', 'editable', 'later'])
      c.editEndpoint(1)
      assert.equal(c.endpointModelForm.priority, 1)
      Object.assign(c.endpointModelForm, { model_id: 'replacement', priority: 1 })
      c.saveEndpoint()
      assert.equal(c.modelForm.endpoints.length, 3)
      assert.deepEqual(JSON.parse(JSON.stringify(c.modelForm.endpoints[1])), {
        endpoint_id: 'editable', model_id: 'replacement', priority: 1,
        enabled: false, capabilities: { tools: true }, rpm: 9,
      })
      assert.equal(JSON.stringify(settings), before)
      c.moveEndpoint(1, -1)
      assert.equal(c.modelForm.endpoints[0].endpoint_id, 'editable')
      c.moveEndpoint(1, 1)
      assert.equal(c.modelForm.endpoints[2].endpoint_id, 'later')
      c.editEndpoint(0)
      c.endpointModelForm.model_id = 'discard'
      c.cancelEndpoint()
      assert.equal(c.modelForm.endpoints[0].model_id, 'replacement')
      c.addEndpoint()
      c.saveEndpoint()
      assert.equal(c.endpointError.value, messages.settings.select_endpoint)
      assert.equal(c.modelForm.endpoints.length, 3)
      c.endpointModelForm.endpoint_id = 'new'
      for (const invalid of [0, -1, 1.5, null, '1']) {
        c.endpointModelForm.priority = invalid
        c.saveEndpoint()
        assert.equal(c.endpointError.value, messages.settings.endpoint_priority_invalid)
        assert.equal(c.modelForm.endpoints.length, 3)
      }
      c.endpointModelForm.priority = 1
      c.saveEndpoint()
      assert.deepEqual(JSON.parse(JSON.stringify(c.modelForm.endpoints[2])), { endpoint_id: 'new', priority: 1 })
      assert.equal(JSON.stringify(settings), before)
      c.cancelModel()
      assert.equal(JSON.stringify(settings), before)
      c.editModel(settings.models.key, 'key')
      c.editEndpoint(0)
      c.endpointModelForm.priority = 2
      c.saveEndpoint()
      c.saveModel()
      assert.equal(settings.models.key.endpoints.find(e => e.endpoint_id === 'legacy').priority, 2)
      assert.equal(settings.models.key.custom_model_option, 'keep')
      c.addNewModel()
      assert.equal('custom_model_option' in c.modelForm, false)
      c.cancelModel()
      return c
    } }, { modelValue: settings, endpoints })
    app.use(createI18n({ legacy: false, locale: 'en', messages: { en: messages } }))
    for (const name of ['ADivider', 'AForm', 'AFormItem', 'ATypographyTitle', 'ATypographyParagraph', 'ATypographyText',
      'AButton', 'ATextarea', 'ASelect', 'AInput', 'AModal', 'AFlex', 'AList', 'AListItem', 'ATooltip',
      'ASwitch', 'AInputNumber', 'ASpace', 'APopover']) {
      app.component(name, { setup: (props, { slots }) => () => h('div', slots.default?.()) })
    }
    await renderToString(app)
    assert.ok(controller)
  } finally { await server.close() }
})

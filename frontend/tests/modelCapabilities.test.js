import assert from 'node:assert/strict'
import test from 'node:test'
import { reactive, computed } from 'vue'
import { resolveModelCapabilities } from '../src/utils/modelCapabilities.js'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createI18n } from 'vue-i18n'
import { createServer } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
import { readFile } from 'node:fs/promises'

test('resolves existing provider aliases and preserves false versus missing settings', () => {
  const backends = { openai: { models: { example: {
    native_multimodal: true, function_call_available: false,
    context_length: 32000, max_output_tokens: null,
  } } } }
  const expected = { native_multimodal: true, function_call_available: false,
    response_format_available: null, context_length: 32000, max_output_tokens: null }
  assert.deepEqual(resolveModelCapabilities(backends, 'OpenAI', 'example'), expected)
  assert.deepEqual(resolveModelCapabilities(backends, 'openai', 'example'), expected)
  assert.ok(Object.values(resolveModelCapabilities(backends, 'missing', 'example')).every(value => value === null))
  assert.ok(Object.values(resolveModelCapabilities(backends, 'OpenAI', 'missing')).every(value => value === null))
  assert.ok(Object.values(resolveModelCapabilities(undefined, '', '')).every(value => value === null))
})

test('local family selections resolve local settings, and model/settings changes remain reactive', () => {
  const state = reactive({ provider: '_local__my-family', model: 'first', backends: {
    local: { models: { first: { native_multimodal: false }, second: { response_format_available: true } } },
  } })
  const result = computed(() => resolveModelCapabilities(state.backends, state.provider, state.model))
  assert.equal(result.value.native_multimodal, false)
  state.model = 'second'
  assert.equal(result.value.native_multimodal, null)
  assert.equal(result.value.response_format_available, true)
  state.backends.local.models.second.function_call_available = false
  assert.equal(result.value.function_call_available, false)
  state.provider = 'local'
  assert.equal(result.value.response_format_available, true)
  delete state.backends.local.models.second
  assert.equal(result.value.response_format_available, null)
})

test('shared summary labels capability states and separates token limits', async () => {
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [vue(), { name: 'capability-settings-fixture', enforce: 'pre',
      resolveId(id) { if (id.replaceAll('\\', '/').endsWith('/stores/userSettings')) return '\0capability-settings-fixture' },
      load(id) { if (id === '\0capability-settings-fixture') return `export const useUserSettingsStore = () => ({setting:{data:{llm_settings:{backends:{local:{models:{example:{native_multimodal:true,function_call_available:false,context_length:32000}}}}}}}})` },
    }],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  try {
    const { default: component } = await server.ssrLoadModule('/src/components/ModelCapabilities.vue')
    const messages = JSON.parse(await readFile(new URL('../src/locales/en-US.json', import.meta.url), 'utf8'))
    const app = createSSRApp(component, { provider: '_local__family', model: 'example' })
    app.use(createI18n({ legacy: false, locale: 'en', messages: { en: messages } }))
    const html = await renderToString(app)
    assert.match(html, /aria-label="Model capabilities"/)
    assert.doesNotMatch(html, /not verified/)
    assert.match(html, /Image input：Supported/)
    assert.match(html, /Native tools：Unsupported/)
    assert.match(html, /JSON mode：Unknown/)
    assert.match(html, /32,000/)
    assert.match(html, /Chat can try calling tools through prompts; workflow nodes require native tool support/)
  } finally { await server.close() }
})

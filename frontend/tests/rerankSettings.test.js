import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { addVekaiPreset, rerankOptions, validRerankSelection } from '../src/components/settings/retrievalSettings.js'

test('Vekai presets persist native vv-llm mapping without enabling rerank or inventing dimensions', () => {
  const settings = { knowledge_retrieval: { rerank: { provider: '', model: '' } } }
  assert.equal(addVekaiPreset(settings, 'rerank', { address: 'http://127.0.0.1:8012', modelId: 'local-reranker' }), true)
  assert.equal(settings.llm_settings.embedding_backends, undefined)
  const saved = JSON.parse(JSON.stringify(settings))
  const backend = saved.llm_settings.rerank_backends.local
  assert.equal(backend.default_endpoint, null)
  assert.deepEqual(backend.models['vekai-rerank'], {
    id: 'local-reranker', enabled: true, endpoints: ['vekai-rerank'], protocol: 'custom_json_http',
    request_mapping: { method: 'POST', path: '/v1/rerank', body_template: {
      model: '${model_id}', query: '${query}', documents: '${documents}', top_n: '${top_n}',
    } },
    response_mapping: { results_path: '$.results[*]', field_map: { index: 'index', relevance_score: 'relevance_score' } },
  })
  assert.deepEqual(saved.knowledge_retrieval.rerank, { provider: '', model: '' })
  assert.equal(addVekaiPreset(settings, 'embedding', { address: 'http://127.0.0.1:8013', modelId: 'local-embedding' }), true)
  const embedding = settings.llm_settings.embedding_backends.local.models['vekai-embedding']
  assert.equal(embedding.protocol, 'openai_embeddings')
  assert.equal(embedding.id, 'local-embedding')
  assert.equal(settings.llm_settings.endpoints.find(endpoint => endpoint.id === 'vekai-embedding').api_base, 'http://127.0.0.1:8013/v1')
  assert.equal(Object.hasOwn(embedding, 'dimensions'), false)
})

test('conflicting endpoint URLs reject the preset without initializing or modifying any draft fields', () => {
  for (const kind of ['embedding', 'rerank']) {
    const settings = { llm_settings: { endpoints: [{
      id: `vekai-${kind}`, api_base: 'http://custom:123', _saved_secret_fields: ['api_key'],
    }] }, knowledge_retrieval: { rerank: { provider: 'custom', model: 'chosen-key' } } }
    const before = structuredClone(settings)
    assert.throws(() => addVekaiPreset(settings, kind, {
      address: 'http://127.0.0.1:8012', modelId: 'my-model',
    }), { message: 'endpoint_conflict' })
    assert.deepEqual(settings, before)
  }
})

test('same-URL endpoints retain credentials and existing model keys are idempotent', () => {
  const settings = { llm_settings: { endpoints: [{
    id: 'vekai-rerank', api_base: 'http://127.0.0.1:8012/', _saved_secret_fields: ['api_key'],
  }] }, knowledge_retrieval: { rerank: { provider: 'custom', model: 'chosen-key' } } }
  const endpoint = structuredClone(settings.llm_settings.endpoints[0])
  assert.equal(addVekaiPreset(settings, 'rerank', { address: 'http://127.0.0.1:8012', modelId: 'my-model' }), true)
  assert.deepEqual(settings.llm_settings.endpoints[0], endpoint)
  assert.equal(settings.llm_settings.endpoints.length, 1)
  settings.llm_settings.rerank_backends.local.models['vekai-rerank'].enabled = false
  const before = structuredClone(settings)
  assert.equal(addVekaiPreset(settings, 'rerank', { address: 'http://different:80', modelId: 'replacement' }), false)
  assert.deepEqual(settings, before)
  assert.deepEqual(settings.knowledge_retrieval.rerank, { provider: 'custom', model: 'chosen-key' })
  delete settings.llm_settings.endpoints
  const missingEndpoint = structuredClone(settings)
  assert.equal(addVekaiPreset(settings, 'rerank', { address: 'invalid', modelId: '' }), false)
  assert.deepEqual(settings, missingEndpoint)
})

test('service roots and /v1 addresses resolve without a duplicate /v1 using vv-llm path concatenation', () => {
  for (const kind of ['embedding', 'rerank']) {
    for (const suffix of ['', '/', '/v1', '/v1/']) {
      const settings = {}
      addVekaiPreset(settings, kind, { address: `http://127.0.0.1:8012${suffix}`, modelId: 'my-model' })
      const base = settings.llm_settings.endpoints[0].api_base
      const path = kind === 'embedding' ? '/embeddings' :
        settings.llm_settings.rerank_backends.local.models['vekai-rerank'].request_mapping.path
      assert.equal(`${base.replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`,
        `http://127.0.0.1:8012/v1/${kind === 'embedding' ? 'embeddings' : 'rerank'}`)
    }
  }
})
test('rerank selection uses model keys, supports off, and rejects disabled or missing models', () => {
  const backends = { local: { models: { key: { id: 'runtime-id' }, disabled: { id: 'disabled', enabled: false } } } }
  assert.deepEqual(rerankOptions(backends)[0].children, [{ value: 'key', label: 'key (runtime-id)' }])
  assert.equal(validRerankSelection(backends, { provider: '', model: '' }), true)
  assert.equal(validRerankSelection(backends, { provider: 'local', model: 'key' }), true)
  for (const model of ['', 'runtime-id', 'disabled', 'missing']) {
    assert.equal(validRerankSelection(backends, { provider: 'local', model }), false)
  }
  assert.equal(validRerankSelection(backends, { provider: '', model: 'key' }), false)
})

test('invalid preset input does not mutate settings', () => {
  for (const address of ['invalid', 'file:///tmp/a', 'http://user:password@localhost:8012']) {
    const settings = {}
    assert.throws(() => addVekaiPreset(settings, 'rerank', { address, modelId: 'local-reranker' }))
    assert.deepEqual(settings, {})
  }
})

test('embedding can be added alone and a custom API base path is preserved', () => {
  const settings = {}
  addVekaiPreset(settings, 'embedding', { address: 'https://example.test/custom/v1/', modelId: 'my-embedding' })
  assert.equal(settings.llm_settings.rerank_backends, undefined)
  assert.equal(settings.llm_settings.endpoints[0].api_base, 'https://example.test/custom/v1')
  assert.equal(settings.llm_settings.embedding_backends.local.models['vekai-embedding'].id, 'my-embedding')
  assert.equal(settings.knowledge_retrieval, undefined)
})

test('new settings tooltips and shared media actions have Chinese and English translations', async () => {
  for (const locale of ['zh-CN', 'en-US']) {
    const messages = JSON.parse(await readFile(new URL(`../src/locales/${locale}.json`, import.meta.url), 'utf8'))
    assert.ok(messages.knowledgeBase.rerank_unavailable, `${locale}: knowledgeBase.rerank_unavailable`)
    for (const key of ['export_table', 'download', 'play', 'pause']) assert.ok(messages.common[key], `${locale}: common.${key}`)
    for (const key of ['expand_menu', 'collapse_menu', 'configure_shortcut', 'rerank_off', 'rerank_invalid', 'vekai_connect', 'vekai_endpoint_conflict']) {
      assert.ok(messages.settings[key], `${locale}: settings.${key}`)
    }
  }
})

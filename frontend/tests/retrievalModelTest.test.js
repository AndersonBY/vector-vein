import assert from 'node:assert/strict'
import test from 'node:test'
import { effectScope, reactive } from 'vue'
import { retrievalTestEndpoints, useRetrievalModelTest } from '../src/utils/retrievalModelTest.js'

const create = request => {
  const input = reactive({ active: true, kind: 'embedding', backend: 'local', modelKey: 'draft',
    modelConfig: { id: 'actual-id', protocol: 'openai_embeddings', endpoints: ['endpoint'] },
    endpoint: { id: 'endpoint', api_base: 'http://localhost:8013/v1', _saved_secret_fields: ['api_key'] },
    binding: { endpoint_id: 'endpoint', model_id: 'override' } })
  const scope = effectScope()
  return { input, scope, ...scope.run(() => useRetrievalModelTest(() => input, request, key => key)) }
}

test('retrieval endpoint selection respects model overrides and defaults without silently changing endpoints', () => {
  const endpoints = [{ id: 'a' }, { id: 'b' }]
  const options = retrievalTestEndpoints({ endpoints: ['missing', { endpoint_id: 'b', model_id: 'override' }] }, 'a', endpoints)
  assert.equal(options[0].endpoint, undefined)
  assert.deepEqual(options[1], { value: '1', label: 'b (override)', endpoint: endpoints[1], binding: { endpoint_id: 'b', model_id: 'override' } })
  assert.equal(retrievalTestEndpoints({}, 'a', endpoints)[0].endpoint.id, 'a')
  assert.deepEqual(retrievalTestEndpoints({}, null, endpoints), [])
})

test('test sends an isolated current draft including credential references and override binding', async () => {
  let call
  const f = create(async (action, payload) => { call = { action, payload }; return { status: 200, data: { kind: 'embedding', dimensions: 768, count: 2, elapsed_ms: 25 } } })
  try {
    const before = JSON.stringify(f.input)
    await f.submit()
    assert.equal(call.action, 'test_retrieval_model')
    assert.equal(call.payload.model_key, 'draft')
    assert.equal(call.payload.binding.model_id, 'override')
    assert.deepEqual(call.payload.endpoint._saved_secret_fields, ['api_key'])
    call.payload.model_config.id = 'changed'
    assert.equal(JSON.stringify(f.input), before)
    assert.equal(f.state.result.dimensions, 768)
  } finally { f.scope.stop() }
})

test('invalid draft, missing endpoint and malformed credentials never send requests', async () => {
  for (const mutate of [f => { f.input.modelConfig = null }, f => { f.input.modelKey = '' }, f => { f.input.endpoint = null }, f => { f.input.endpoint.credentials = 'malformed-private-data' }]) {
    const f = create(() => assert.fail('should not request'))
    try { mutate(f); await f.submit(); assert.ok(f.state.error); assert.doesNotMatch(f.state.error, /private-data/) } finally { f.scope.stop() }
  }
})

test('closing, changing a draft or unmounting discards late test results', async () => {
  for (const mutate of [f => { f.input.active = false }, f => { f.input.modelConfig.id = 'new' }, f => { f.input.endpoint.api_base = 'http://new.invalid' }, f => f.scope.stop()]) {
    let done
    const f = create(() => new Promise(resolve => { done = resolve }))
    try {
      const pending = f.submit(); mutate(f); done({ status: 200, data: { kind: 'embedding' } }); await pending
      assert.equal(f.state.result, null); assert.equal(f.state.loading, false)
    } finally { f.scope.stop() }
  }
})

test('duplicate requests are blocked and safe categorized errors do not expose provider messages', async () => {
  let done, calls = 0
  const f = create(() => { calls++; return new Promise(resolve => { done = resolve }) })
  try {
    const pending = f.submit(); await f.submit(); assert.equal(calls, 1)
    done({ status: 502, data: { error_code: 'auth_failed' }, msg: 'secret-provider-message' }); await pending
    assert.equal(f.state.error, 'settings.retrieval_test_error_auth_failed'); assert.equal(f.state.loading, false)
  } finally { f.scope.stop() }
})

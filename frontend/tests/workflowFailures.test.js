import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createI18n } from 'vue-i18n'
import { createServer } from 'vite'
import vue from '@vitejs/plugin-vue'
import { getWorkflowFailures, getWorkflowRunStatus, getWorkflowTaskTitleKey, getWorkflowFailureSnapshot } from '../src/utils/workflowFailures.js'

test('workflow failures preserve concrete plain-text evidence and custom node names', () => {
  const snapshot = {
    nodes: [{ id: 'node-1', data: { title: 'Send invoice' } }],
    failures: [{ node_id: 'node-1', task_name: 'tools.http', code: 'NODE_EXECUTION_FAILED',
      exception_type: 'ValueError', message: '<script>alert(1)</script>\nInvalid URL' }],
  }
  assert.deepEqual(getWorkflowFailures(snapshot), [{
    nodeId: 'node-1', nodeName: 'Send invoice', taskName: 'tools.http',
    code: 'NODE_EXECUTION_FAILED', exceptionType: 'ValueError', message: '<script>alert(1)</script>\nInvalid URL',
  }])
  assert.equal(getWorkflowRunStatus({ status: 500, data: { data: snapshot } }), 'FAILED')
  assert.equal(getWorkflowRunStatus({ status: 200, data: { data: snapshot } }), 'FAILED')
})

test('failure projection tolerates missing, malformed and legacy records without raw object dumps', () => {
  for (const value of [null, undefined, '', { failures: {} }, { failures: [null, 'oops', {}] }]) {
    assert.deepEqual(getWorkflowFailures(value), [])
  }
  assert.deepEqual(getWorkflowFailures({ error_task: 'llms.open_ai' }), [{ taskName: 'llms.open_ai' }])
  assert.deepEqual(getWorkflowFailures({ error_task: { headers: 'private' } }), [])
  const [failure] = getWorkflowFailures({ failures: [{ message: { headers: 'private' }, node_id: '1' }] })
  assert.equal(failure.message, '')
  assert.equal(getWorkflowTaskTitleKey('llms.open_ai'), 'components.nodes.llms.OpenAI.title')
  assert.equal(getWorkflowTaskTitleKey('vector_db.search_data'), 'components.nodes.vectorDb.Search.title')
  for (const task of [null, {}, 'invalid', '']) assert.equal(getWorkflowTaskTitleKey(task), '')
})

test('failure evidence is bounded and successful or pending polling stays distinct', () => {
  const failures = getWorkflowFailures({ failures: Array.from({ length: 20 }, () => ({ message: 'x'.repeat(2000) })) })
  assert.equal(failures.length, 8)
  assert.equal(failures[0].message.length, 1500)
  assert.equal(getWorkflowRunStatus({ status: 200, data: { data: { failures: [] } } }), 'FINISHED')
  assert.equal(getWorkflowRunStatus({ status: 202 }), '')
  assert.equal(getWorkflowRunStatus({ status: 200, data: { status: 'FAILED' } }), 'FAILED')
})

test('chat history reads structured failure metadata and tolerates old text output', () => {
  const payload = { status: 'FAILED', error_task: 'llms.open_ai', failures: [{ message: 'Model unavailable' }] }
  const result = JSON.stringify(payload)
  for (const snapshot of [undefined, {}, { nodes: [] }, { failures: [] }]) {
    assert.equal(getWorkflowFailures(getWorkflowFailureSnapshot(snapshot, result))[0].message, 'Model unavailable')
  }
  const storedSnapshot = { failures: [{ message: 'Stored error' }] }
  assert.equal(getWorkflowFailureSnapshot(storedSnapshot, result), storedSnapshot)
  for (const value of ['# Old workflow output', 'null', '', undefined]) {
    assert.deepEqual(getWorkflowFailureSnapshot(undefined, value), {})
  }
})

test('failure details render malicious provider text as escaped text, including fallback records', async () => {
  const server = await createServer({
    configFile: false,
    root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [vue()],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true },
    optimizeDeps: { noDiscovery: true },
    appType: 'custom',
  })
  try {
    const { default: component } = await server.ssrLoadModule('/src/components/workspace/WorkflowFailureDetails.vue')
    const messages = JSON.parse(await readFile(new URL('../src/locales/en-US.json', import.meta.url), 'utf8'))
    const render = async snapshot => {
      const app = createSSRApp(component, { snapshot })
      app.use(createI18n({ legacy: false, locale: 'en', messages: { en: messages } }))
      return renderToString(app)
    }
    const html = await render({ failures: [{ node_id: 'http-1', node_name: '<b>Request</b>',
      message: '<script>alert(1)</script>\nBad endpoint', exception_type: 'ValueError' }] })
    assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/)
    assert.match(html, /&lt;b&gt;Request&lt;\/b&gt;/)
    assert.match(html, /ValueError/)
    assert.doesNotMatch(html, /<script>|<b>Request/)
    assert.match(await render({ error_task: 'llms.open_ai' }), /OpenAI/)
    assert.match(await render({}), /This record has no detailed error message/)
  } finally {
    await server.close()
  }
})

test('stopped responses remain cancellation even with partial node failures', () => {
  for (const response of [
    { status: 200, msg: 'STOPPED', data: { data: { failures: [{ message: 'partial failure' }] } } },
    { status: 200, data: { status: 'STOPPED' } },
  ]) assert.equal(getWorkflowRunStatus(response), 'STOPPED')
  assert.equal(getWorkflowRunStatus({ status: 202, msg: 'STOPPING' }), '')
})

test('paused workflow snapshots remain nonterminal, even with previous partial failure evidence', () => {
  assert.equal(getWorkflowRunStatus({status:200,data:{status:'PAUSED'}}), '')
  assert.equal(getWorkflowRunStatus({status:102,msg:'PAUSED',data:{data:{failures:[{message:'partial'}]}}}), '')
})

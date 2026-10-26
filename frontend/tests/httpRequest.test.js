import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
import { createTemplateData } from '../src/components/nodes/tools/HttpRequest.js'

test('HTTP request template matches request and response contract', () => {
  const data = createTemplateData()
  assert.equal(data.task_name, 'tools.http_request')
  assert.equal(data.has_inputs, true)
  const fields = data.template
  assert.deepEqual(Object.keys(fields), ['method', 'url', 'headers', 'query_params', 'body_type', 'body',
    'timeout', 'follow_redirects', 'fail_on_http_error', 'status_code', 'response_headers', 'response_body', 'response_json'])
  assert.equal(fields.url.required, true)
  assert.equal(fields.url.type, 'str')
  assert.equal(fields.url.value, '')
  assert.equal(fields.method.value, 'GET')
  assert.deepEqual(fields.method.options.map(item => item.value), ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'])
  for (const name of ['headers', 'query_params']) {
    assert.equal(fields[name].value, '{}')
    assert.equal(fields[name].type, 'dict|str')
    assert.equal(fields[name].field_type, 'textarea')
  }
  assert.equal(fields.body_type.value, 'none')
  assert.deepEqual(fields.body_type.options.map(item => item.value), ['none', 'json', 'text', 'form'])
  assert.equal(fields.body.field_type, 'textarea')
  assert.equal(fields.body.type, 'any')
  assert.deepEqual([fields.timeout.value, fields.timeout.min, fields.timeout.max], [30, 1, 300])
  assert.equal(fields.follow_redirects.value, false)
  assert.equal(fields.fail_on_http_error.value, true)
  assert.deepEqual(Object.values(fields).filter(item => item.is_output).map(item => [item.name, item.type]),
    [['status_code', 'int'], ['response_headers', 'dict'], ['response_body', 'str'], ['response_json', 'any']])
  assert.equal(fields.response_json.value, null)
  assert.deepEqual(Object.values(fields).filter(item => !item.is_output && !item.group).map(item => item.name), ['method', 'url'])
})

test('HTTP request instances never share options or response objects', () => {
  const first = createTemplateData().template
  const second = createTemplateData().template
  first.method.options[0].label = 'Changed'
  first.body_type.options.push({ value: 'other' })
  first.response_headers.value.test = 'changed'
  assert.equal(second.method.options[0].label, 'GET')
  assert.equal(second.body_type.options.length, 4)
  assert.deepEqual(second.response_headers.value, {})
})

test('HTTP request is exposed by the manifest with complete English and Chinese labels', async () => {
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  try {
    const { plannedNodeManifest } = await server.ssrLoadModule('/src/config/nodeManifest.js')
    assert.deepEqual(plannedNodeManifest.HttpRequest, {
      category: 'tools', frontendComponent: 'HttpRequest', backendTask: 'tools.http_request',
      featureFlag: null, tags: ['http', 'api', 'request'], status: 'available',
    })
  } finally {
    await server.close()
  }
  for (const locale of ['en-US', 'zh-CN']) {
    const messages = JSON.parse(await readFile(new URL(`../src/locales/${locale}.json`, import.meta.url), 'utf8'))
    const labels = messages.components.nodes.tools.HttpRequest
    for (const name of ['title', 'description', ...Object.keys(createTemplateData().template),
      ...['none', 'json', 'text', 'form'].map(value => `body_type_${value}`),
      'headers_tip', 'query_params_tip', 'body_tip', 'fail_on_http_error_tip', 'response_json_tip']) {
      assert.equal(typeof labels[name], 'string', `${locale}: ${name}`)
      assert.ok(labels[name].length > 0)
    }
  }
})

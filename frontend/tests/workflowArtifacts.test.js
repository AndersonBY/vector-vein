import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createI18n } from 'vue-i18n'
import { createServer } from 'vite'
import vue from '@vitejs/plugin-vue'
import { Button, Space } from 'ant-design-vue'
import { createRunArtifacts, formatArtifactSize, artifactSourceLabel } from '../src/utils/workflowArtifacts.js'

const artifact = { path: '/output/report.pdf', name: 'report.pdf', size: 2048, exists: true, parent_exists: true, sources: [] }
const success = artifacts => ({ status: 200, data: { artifacts } })
test('run switching immediately clears files and pending actions, rejecting late lists and actions', async () => {
  const requests = []
  let state
  const files = createRunArtifacts((action, payload) => new Promise(resolve => requests.push({ action, payload, resolve })), value => { state = value })
  const first = files.select('first')
  requests[0].resolve(success([artifact])); await first
  const opening = files.open(artifact, 'open')
  assert.equal(state.pending, artifact.path)
  assert.deepEqual(requests[1].payload, { rid: 'first', path: artifact.path, action: 'open' })
  const second = files.select('second')
  assert.deepEqual(state.artifacts, [])
  assert.equal(state.pending, '')
  requests[1].resolve({ status: 404 }); await opening
  assert.equal(state.error, '')
  const latest = files.refresh()
  requests[3].resolve(success([{ ...artifact, name: 'current.pdf' }])); await latest
  requests[2].resolve(success([artifact])); await second
  assert.equal(state.artifacts[0].name, 'current.pdf')
  const late = files.refresh(); files.dispose()
  requests[4].resolve(success([])); await late
  assert.equal(state.artifacts.length, 1)
})

test('missing file blocks Open, permits its existing parent, and failed actions refetch availability safely', async () => {
  const calls = []
  let state, fail = false
  const missing = { ...artifact, exists: false }
  const files = createRunArtifacts(async (action, payload) => {
    calls.push({ action, payload })
    if (action === 'list_artifacts') return success([fail ? missing : artifact])
    if (fail) throw new Error('secret absolute path and exception')
    return { status: 200 }
  }, value => { state = value })
  await files.select('run')
  fail = true
  await files.open(artifact, 'open')
  assert.equal(state.error, 'open')
  assert.equal(state.artifacts[0].exists, false)
  const before = calls.length
  await files.open(missing, 'open')
  assert.equal(calls.length, before)
  fail = false
  await files.open(missing, 'folder')
  assert.deepEqual(calls.at(-1), { action: 'open_artifact', payload: { rid: 'run', path: artifact.path, action: 'folder' } })
  assert.equal(state.error, '')
})

test('list failure is retryable without exposing exception text; empty successful list stays empty', async () => {
  let state, fail = true
  const files = createRunArtifacts(async () => {
    if (fail) throw new Error('private diagnostic')
    return success([])
  }, value => { state = value })
  await files.select('run'); assert.equal(state.error, 'list')
  fail = false; await files.refresh()
  assert.deepEqual(state, { artifacts: [], error: '', pending: '' })
})

test('file sizes and typed node source labels preserve custom names and localized titles', () => {
  assert.equal(formatArtifactSize(null), '—')
  assert.equal(formatArtifactSize(0), '0 B')
  assert.equal(formatArtifactSize(2048), '2.0 KB')
  assert.equal(artifactSourceLabel({ node_type: 'Document' }, () => '文档', key => key === 'components.nodes.outputs.Document.title'), '文档')
  assert.equal(artifactSourceLabel({ title: '<script>name</script>' }, () => '', () => false), '<script>name</script>')
})

test('component is SSR safe with no empty file section or browser API access; output integration remains outside debug toggle', async () => {
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)), plugins: [vue()],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  try {
    const { default: component } = await server.ssrLoadModule('/src/components/workspace/WorkflowRunArtifacts.vue')
    for (const locale of ['en-US', 'zh-CN']) {
      const messages = JSON.parse(await readFile(new URL(`../src/locales/${locale}.json`, import.meta.url), 'utf8'))
      const app = createSSRApp(component, { rid: 'run' })
      app.use(Button).use(Space)
      app.use(createI18n({ legacy: false, locale, messages: { [locale]: messages } }))
      assert.doesNotMatch(await renderToString(app), /<section|report.pdf|pywebview/)
      assert.ok(messages.workspace.workflowSpace.artifact_missing)
    }
    const source = await readFile(new URL('../src/components/workspace/WorkflowUse.vue', import.meta.url), 'utf8')
    assert.match(source, /const showTimeline = ref\(false\)/)
    assert.match(source, /<WorkflowRunArtifacts v-if="runRecordId && \(running \|\| showingRecord\)"/)
  } finally { await server.close() }
})

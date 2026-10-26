import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createI18n } from 'vue-i18n'
import { createServer } from 'vite'
import vue from '@vitejs/plugin-vue'
import { Collapse } from 'ant-design-vue'
import { getWorkflowRunStatus } from '../src/utils/workflowFailures.js'
import { getWorkflowTimeline, getTimelineNodeLabel } from '../src/utils/workflowTimeline.js'

const nodes = ['a', 'b', 'c'].map(id => ({ id, category: 'tools', type: 'HttpRequest', data: {} }))
test('parallel running nodes retain independent states and measured timing', () => {
  const rows = getWorkflowTimeline({ nodes, node_timeline: {
    a: { status: 'SUCCEEDED', started_at: 1000, finished_at: 3000 },
    b: { status: 'RUNNING', started_at: 2000 },
    c: { status: 'WAITING', started_at: 4000 },
  } }, { active: true, now: 6000 })
  assert.deepEqual(rows.map(row => row.status), ['SUCCEEDED', 'RUNNING', 'WAITING'])
  assert.deepEqual(rows.map(row => row.elapsed), [2, 4, 2])
})
test('old records preserve concrete status but invent neither timestamps nor durations', () => {
  const rows = getWorkflowTimeline({ nodes: [
    { ...nodes[0], data: { status: 200 }, run_time: 1.5 },
    { ...nodes[1], data: { status: 500 } }, nodes[2],
  ], failures: [{ node_id: 'b' }] }, { status: 'FAILED' })
  assert.deepEqual(rows.map(row => row.status), ['SUCCEEDED', 'FAILED', 'NOT_RUN'])
  assert.deepEqual(rows.map(row => row.elapsed), [1.5, null, null])
  assert.ok(rows.every(row => row.startedAt === null && row.finishedAt === null))
  assert.equal(getWorkflowTimeline({ nodes: [nodes[0]], node_run_time: { a: 2 } })[0].status, 'UNKNOWN')
})
test('skipped is distinct from unstarted and fresh run discards old evidence', () => {
  const snapshot = { nodes, skipped_nodes: ['a'], node_timeline: { b: { status: 'PENDING' }, c: { status: 'FAILED', run_time: 2 } } }
  assert.deepEqual(getWorkflowTimeline(snapshot, { status: 'FAILED' }).map(row => row.status), ['SKIPPED', 'NOT_RUN', 'FAILED'])
  assert.ok(getWorkflowTimeline(snapshot, { active: true, fresh: true }).every(row => row.status === 'PENDING' && row.elapsed === null))
})
test('execution exclusions and localized labels match node identity', () => {
  const rows = getWorkflowTimeline({ nodes: [...nodes, { id: 'ignore', ignored: true }, { id: 'trigger', category: 'triggers' }, { id: 'note', category: 'assistedNodes' }] })
  assert.equal(rows.length, 3)
  assert.equal(getTimelineNodeLabel(rows[0], () => 'HTTP request', () => true), 'HTTP request')
  assert.equal(getTimelineNodeLabel({ ...rows[0], title: '<script>custom</script>' }, () => '', () => false), '<script>custom</script>')
  assert.equal(getTimelineNodeLabel(rows[0], () => '', () => false), 'HttpRequest')
})
test('new pending entries override stale history evidence, and malformed legacy collections are safe', () => {
  const snapshot = { nodes: [{ ...nodes[0], run_time: 90, data: { status: 200 } }], node_run_time: { a: 80 },
    node_timeline: { a: { status: 'PENDING', run_time: null } }, failures: [null], skipped_nodes: {} }
  const [live] = getWorkflowTimeline(snapshot, { active: true })
  assert.equal(live.status, 'PENDING')
  assert.equal(live.elapsed, null)
  assert.equal(getWorkflowTimeline(snapshot, { status: 'FINISHED' })[0].status, 'UNKNOWN')
  assert.equal(getWorkflowTimeline({ nodes, failures: [null], skipped_nodes: {} })[0].status, 'UNKNOWN')
})
test('poll lifecycle invalidates late requests, retries errors, and never stacks intervals', async () => {
  const source = await readFile(new URL('../src/components/workspace/WorkflowUse.vue', import.meta.url), 'utf8')
  const script = source.match(/function stopStatusPolling\(\) \{[\s\S]*?\n\}/)[0] + '\n' + source.match(/function startStatusPolling\(\) \{[\s\S]*?\n\}/)[0]
  let next = 0
  const timers = new Set()
  let closed = 0
  const sockets = new Set([{ close() { closed++ } }])
  const harness = new Function('setInterval', 'clearInterval', 'runSockets', `${script}; let pollEpoch = 0; const checkingStatus = {value: false}; const checkStatusTimer = {value: null}; const checkWorkflowRunningStatus = () => {}; return { startStatusPolling, stopStatusPolling, epoch: () => pollEpoch };`)(() => { timers.add(++next); return next }, id => timers.delete(id), sockets)
  harness.startStatusPolling()
  harness.startStatusPolling()
  assert.equal(timers.size, 1)
  const capturedEpoch = harness.epoch()
  harness.stopStatusPolling()
  assert.equal(timers.size, 0)
  assert.notEqual(capturedEpoch, harness.epoch())
  assert.equal(closed, 1)
  assert.equal(sockets.size, 0)
  assert.match(source, /if \(epoch !== pollEpoch \|\| rid !== runRecordId.value\) return/)
  assert.match(source, /if \(epoch === pollEpoch\) checkingStatus.value = false/)
  assert.match(source, /\['RUNNING', 'QUEUED'\]\.includes\(record.status\)/)
})

test('real polling code ignores late history responses and retries a temporary network failure', async () => {
  const source = await readFile(new URL('../src/components/workspace/WorkflowUse.vue', import.meta.url), 'utf8')
  const polling = source.slice(source.indexOf('let pollEpoch = 0'), source.indexOf('const runWorkflowVersionModal'))
  const requests = []
  const timers = new Set()
  let timerId = 0
  const ref = value => ({ value })
  const api = () => new Promise((resolve, reject) => requests.push({ resolve, reject }))
  const harness = new Function('ref', 'workflowAPI', 'getWorkflowRunStatus', 'setInterval', 'clearInterval', `
    const runRecordId = ref('first'), checkStatusTimer = ref(null), outputNodes = ref([]), recordStatus = ref('RUNNING');
    const message = {error() {}}, t = value => value;
    ${polling}
    return { poll: checkWorkflowRunningStatus, timelineSnapshot, checkingStatus, recordStatus,
      select(id) { stopStatusPolling(); runRecordId.value = id; timelineSnapshot.value = {nodes: []}; startStatusPolling() } };
  `)(ref, api, getWorkflowRunStatus, () => { timers.add(++timerId); return timerId }, id => timers.delete(id))
  const old = harness.poll()
  harness.select('second')
  const current = harness.poll()
  requests[0].resolve({ status: 202, data: { node_timeline: { stale: { status: 'RUNNING' } } } })
  await old
  assert.equal(harness.timelineSnapshot.value.node_timeline, undefined)
  assert.equal(harness.checkingStatus.value, true)
  requests[1].reject(new Error('temporary outage'))
  await current
  assert.equal(harness.checkingStatus.value, false)
  assert.equal(timers.size, 1)
  const retry = harness.poll()
  requests[2].resolve({ status: 202, msg: 'QUEUED', data: { finished_nodes: [], node_timeline: { second: { status: 'PENDING' } } } })
  await retry
  assert.equal(harness.timelineSnapshot.value.node_timeline.second.status, 'PENDING')
  assert.equal(harness.recordStatus.value, 'QUEUED')
})

test('timeline component renders localized names and escapes custom labels', async () => {
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)), plugins: [vue()],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  try {
    const { default: component } = await server.ssrLoadModule('/src/components/workspace/WorkflowRunTimeline.vue')
    const messages = JSON.parse(await readFile(new URL('../src/locales/en-US.json', import.meta.url), 'utf8'))
    const app = createSSRApp(component, { snapshot: { nodes: [{ ...nodes[0], data: { title: '<script>name</script>' } }, nodes[1]] } })
    app.use(Collapse)
    app.use(createI18n({ legacy: false, locale: 'en', messages: { en: messages } }))
    const html = await renderToString(app)
    assert.match(html, /&lt;script&gt;name&lt;\/script&gt;/)
    assert.doesNotMatch(html, /<script>name/)
    assert.match(html, /HTTP request/)
    assert.match(html, /Unknown/)
  } finally { await server.close() }
})

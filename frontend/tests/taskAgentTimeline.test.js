import test from 'node:test'
import assert from 'node:assert/strict'
import { interactionAnswer, interactionTarget, mergeTaskTimeline, taskNeedsPolling } from '../src/utils/taskAgentTimeline.js'

test('question responses preserve the displayed identity and distinguish free text from selections', () => {
  const question = { kind: 'user', sessionId: 'root', turnId: 'turn', generation: 3, interactionId: 'q1', operationId: 'op', attempt: 1, requestDigest: 'digest', answerSpec: { kind: 'single', options: ['Markdown', 'Text'], allowCustomOptions: false } }
  assert.deepEqual(interactionTarget(question), { sessionId: 'root', turnId: 'turn', generation: 3, interactionId: 'q1', operationId: 'op', attempt: 1, requestDigest: 'digest' })
  assert.deepEqual(interactionAnswer(question, ['Markdown'], ''), { kind: 'single', selected: ['Markdown'], custom: [] })
  assert.deepEqual(interactionAnswer(question, ['Markdown'], ' explain '), { kind: 'text', text: 'explain' })
  assert.equal(interactionAnswer(question, ['unlisted'], ''), null)
  assert.equal(interactionAnswer(question, ['Markdown', 'Text'], ''), null)
  assert.equal(interactionAnswer(question, [], ''), null)
  assert.deepEqual(interactionAnswer({ ...question, answerSpec: { ...question.answerSpec, kind: 'multi' } }, ['Markdown', 'Text'], ''), { kind: 'multi', selected: ['Markdown', 'Text'], custom: [] })
})

test('task history keeps intermediate replies and legacy replies without repeating the final message', () => {
  const messages = [{ mid: 'u', turn_id: 'turn', role: 'user', content: 'Goal', created_at: '2026-11-04T00:00:00Z' }, { mid: 'a', turn_id: 'turn', role: 'assistant', content: 'Result', created_at: '2026-11-04T00:00:03Z' }, { mid: 'old', turn_id: 'legacy', role: 'assistant', content: 'Older', created_at: '2026-11-03T00:00:00Z' }]
  const timeline = [{ id: 'p', turn_id: 'turn', kind: 'assistant', text: 'Working', created_at: '2026-11-04T00:00:01Z' }, { id: 'r', turn_id: 'turn', kind: 'assistant', text: 'Result', created_at: '2026-11-04T00:00:02Z' }]
  assert.deepEqual(mergeTaskTimeline(messages, timeline).map(item => item.text), ['Older', 'Goal', 'Working', 'Result'])
  assert.equal(messages.length, 3)
})

test('waiting, paused and disconnected tasks stay refreshable', () => {
  for (const status of ['PROCESSING', 'WAITING_FOR_USER', 'WAITING_FOR_APPROVAL', 'PAUSED']) assert.equal(taskNeedsPolling(status), true)
  assert.equal(taskNeedsPolling('COMPLETED'), false)
  assert.equal(taskNeedsPolling('COMPLETED', true), true)
})


test('command status preserves uncertain process outcomes instead of showing tool success', async () => {
  const { commandStatus, toolStatusKey } = await import('../src/utils/taskAgentTimeline.js')
  assert.equal(commandStatus({ tool_name: 'bash', status: 'success', result: { preview: '{"status":"unknown"}' } }), 'unknown')
  assert.equal(commandStatus({ tool_name: 'check_background_command', result: { preview: '{"status":"running"}' } }), 'running')
  assert.equal(commandStatus({ tool_name: 'bash', result: { preview: '{"status":"completed"}', truncated: true } }), null)
  assert.equal(commandStatus({ tool_name: 'bash', command_status: 'unknown', result: { preview: '{"status":"running"}' } }), 'unknown')
  assert.equal(commandStatus({ tool_name: 'write_file', result: { preview: '{"status":"unknown"}' } }), null)
  assert.equal(toolStatusKey({ tool_name: 'check_background_command', status: 'error' }), 'command_query_failed')
  assert.equal(toolStatusKey({ tool_name: 'bash', status: 'error' }), 'tool_status_error')
  assert.equal(toolStatusKey({ tool_name: 'check_background_command', status: 'success' }), 'tool_status_success')
})


test('compact activities preserve replies, turn boundaries, failures and stable group keys', async () => {
  const { taskActivityRows } = await import('../src/utils/taskAgentTimeline.js')
  const entries = [{ id: 'user', kind: 'user', turn_id: 'one' }, { id: 'a', kind: 'tool', turn_id: 'one', status: 'success' },
    { id: 'b', kind: 'tool', turn_id: 'one', status: 'error' }, { id: 'reply', kind: 'assistant', turn_id: 'one' },
    { id: 'c', kind: 'tool', turn_id: 'one' }, { id: 'd', kind: 'tool', turn_id: 'two' }, { id: 'child', kind: 'sub_agent', turn_id: 'two' }]
  const rows = taskActivityRows(entries)
  assert.deepEqual(rows.map(row => row.kind), ['user', 'activity', 'assistant', 'activity', 'activity', 'sub_agent'])
  assert.deepEqual(rows[1].entries.map(item => item.id), ['a', 'b'])
  assert.equal(rows[1].entries[1].status, 'error')
  assert.equal(taskActivityRows([...entries, { id: 'e', kind: 'tool', turn_id: 'two' }])[1].id, rows[1].id)
})


test('user messages with equal timestamps keep submission order ahead of their responses', () => {
  const created_at = '2026-11-04T10:00:00Z'
  const messages = [{ mid: 'first', role: 'user', content: 'First', created_at }, { mid: 'second', role: 'user', content: 'Second', created_at }]
  const result = mergeTaskTimeline(messages, [{ id: 'reply', kind: 'assistant', text: 'Answer', created_at }])
  assert.deepEqual(result.map(entry => entry.id), ['first', 'second', 'reply'])
})


test('only finished turns collapse; questions, replies and failures stay inspectable', async () => {
  const { taskConversationRows } = await import('../src/utils/taskAgentTimeline.js')
  const item = (id, kind, extra = {}) => ({ id, kind, turn_id: 'one', created_at: '2026-11-05T01:00:00Z', ...extra })
  const entries = [item('goal', 'user'), item('working', 'assistant'), item('tool', 'tool', { status: 'success', cycle: 1 }),
    item('question', 'question'), item('answer', 'user', { turn_id: 'reply/answer' }), item('write', 'tool', { status: 'success', cycle: 2 }),
    item('final', 'assistant', { final: true, created_at: '2026-11-05T01:00:10Z' }), item('next', 'user', { turn_id: 'two' }),
    item('pending', 'tool', { turn_id: 'two', status: 'running' })]
  const rows = taskConversationRows(entries)
  assert.deepEqual(rows.map(r => r.kind), ['user', 'history', 'question', 'user', 'history', 'assistant', 'user', 'activity'])
  assert.equal(rows[1].attention, false)
  assert.equal(rows[4].duration, 10)
  assert.equal(rows[4].cycles, 1)
  assert.deepEqual(rows[1].entries.map(r => r.id), ['working', 'tool'])
  assert.equal(taskConversationRows(entries.slice(0, 6)).some(r => r.kind === 'history'), false)
  const uncertain = taskConversationRows([item('bad', 'tool', { tool_name: 'bash', status: 'success', command_status: 'unknown' }), item('done', 'assistant', { final: true })])
  assert.equal(uncertain[0].attention, true)
  assert.equal(entries[1].kind, 'assistant')
})

test('command presentation separates stdout from the original receipt without inventing success', async () => {
  const { toolResultPresentation } = await import('../src/utils/taskAgentTimeline.js')
  const receipt = { status: 'completed', exit_code: 0, output: '', elapsed_seconds: 2 }
  const result = toolResultPresentation({ tool_name: 'bash' }, JSON.stringify(receipt))
  assert.deepEqual(result.command, receipt)
  assert.equal(result.text, '')
  assert.deepEqual(JSON.parse(result.raw), receipt)
  const unknown = toolResultPresentation({ tool_name: 'check_background_command' }, '{"status":"unknown","output":"partial"}')
  assert.equal(unknown.command.status, 'unknown')
  assert.equal(unknown.command.exit_code, undefined)
  assert.equal(toolResultPresentation({ tool_name: 'bash' }, '{"status":').command, undefined)
  assert.equal(toolResultPresentation({ tool_name: 'write_file' }, JSON.stringify(receipt)).command, undefined)
})


test('Project file links stay local while external links remain external', async () => {
  const { taskFileLink } = await import('../src/utils/taskAgentTimeline.js')
  assert.equal(taskFileLink('project-files/1/src/test.py', true), 'project-files/1/src/test.py')
  assert.equal(taskFileLink('README.md', true), 'README.md')
  assert.equal(taskFileLink('README.md'), null)
  assert.equal(taskFileLink('https://example.com/report.md', true), null)
  assert.equal(taskFileLink('//example.com/report.md', true), null)
  assert.equal(taskFileLink('#heading', true), null)
  assert.equal(taskFileLink('./outputs/report.md'), 'outputs/report.md')
  for (const project of [false, true]) {
    assert.equal(taskFileLink('.knowledge/Notes/report.pdf', project), '.knowledge/Notes/report.pdf')
    assert.equal(taskFileLink('./.knowledge/Notes/report.pdf', project), '.knowledge/Notes/report.pdf')
    assert.equal(taskFileLink('.knowledge/Notes/My%20report.pdf', project), '.knowledge/Notes/My%20report.pdf')
    for (const path of ['.knowledge/../secret', '.knowledge\\Notes\\a.pdf', '%2eknowledge/Notes/a.pdf',
      '.knowledge/Notes/%2e%2e/a.pdf', 'project-files/1/.knowledge/Notes/a.pdf', '.knowledge//a.pdf']) {
      assert.equal(taskFileLink(path, project), null, path)
    }
  }
})

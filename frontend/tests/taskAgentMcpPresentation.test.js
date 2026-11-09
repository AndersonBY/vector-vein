import assert from 'node:assert/strict'
import test from 'node:test'
import { taskConversationRows } from '../src/utils/taskAgentTimeline.js'

for (const outcome of [
  { status: 'unknown' },
  { status: 'success', mcp_run: { status: 'UNKNOWN', dispatch_uncertain: true } },
]) {
  test(`completed conversation keeps attention on uncertain MCP outcome (${outcome.status})`, () => {
    const rows = taskConversationRows([
      {
        id: 'mcp-call', kind: 'tool', turn_id: 'task/turn/1',
        tool_name: 'mcp__test__write_remote__abc', ...outcome,
        created_at: '2026-11-06T00:00:00Z',
      },
      {
        id: 'final', kind: 'assistant', turn_id: 'task/turn/1',
        text: 'The remote outcome is unconfirmed.', final: true,
        created_at: '2026-11-06T00:00:01Z',
      },
    ])
    assert.equal(rows[0].kind, 'history')
    assert.equal(rows[0].attention, true)
    assert.equal(rows[0].entries[0].id, 'mcp-call')
    assert.equal(rows[1].id, 'final')
  })
}

test('isParkedMcpWait detects active-turn UNKNOWN MCP runs for FAILED and cached PROCESSING without matching old turns or missing turn identity', async () => {
  const { isParkedMcpWait, toolDisplaySummary, toolResultPresentation, toolStatusKey } = await import('../src/utils/taskAgentTimeline.js')
  const taskFailed = { tid: 't1', status: 'FAILED', current_turn_id: 't1/turn/2' }
  const taskProcessing = { tid: 't1', status: 'PROCESSING', current_turn_id: 't1/turn/2' }
  const currentUnknown = [{ job_id: 'j2', turn_id: 't1/turn/2', status: 'UNKNOWN', dispatch_uncertain: true }]

  // Current turn UNKNOWN in FAILED and cached PROCESSING
  assert.equal(isParkedMcpWait(taskFailed, { waitKind: 'provider' }, currentUnknown), true)
  assert.equal(isParkedMcpWait(taskProcessing, { waitKind: 'provider' }, currentUnknown), true)

  // Settled or non-provider waitKind
  assert.equal(isParkedMcpWait({ ...taskFailed, status: 'INTERRUPTED' }, { waitKind: 'provider' }, currentUnknown), false)
  assert.equal(isParkedMcpWait(taskFailed, { waitKind: null }, currentUnknown), false)

  // Current turn confirmed FINISHED or still ADMITTED/DISPATCHING
  assert.equal(isParkedMcpWait(taskFailed, { waitKind: 'provider' }, [{ job_id: 'j2', turn_id: 't1/turn/2', status: 'FINISHED', dispatch_uncertain: false }]), false)
  assert.equal(isParkedMcpWait(taskProcessing, { waitKind: 'provider' }, [
    ...currentUnknown,
    { job_id: 'j3', turn_id: 't1/turn/2', status: 'DISPATCHING', dispatch_uncertain: false },
  ]), false)

  // Old-turn unknown must NOT block a new turn
  const oldUnknownOnly = [{ job_id: 'j1', turn_id: 't1/turn/1', status: 'UNKNOWN', dispatch_uncertain: true }]
  assert.equal(isParkedMcpWait(taskProcessing, { waitKind: 'provider' }, oldUnknownOnly), false)
  assert.equal(isParkedMcpWait(taskFailed, { waitKind: 'provider' }, oldUnknownOnly), false)

  // Missing current_turn_id must NOT fall back to all historical runs
  assert.equal(isParkedMcpWait({ tid: 't1', status: 'FAILED', current_turn_id: '' }, { waitKind: 'provider' }, currentUnknown), false)
  assert.equal(isParkedMcpWait({ tid: 't1', status: 'FAILED' }, { waitKind: 'provider' }, currentUnknown), false)

  // activate_skill display summary
  assert.equal(toolDisplaySummary({ tool_name: 'activate_skill', arguments: { skill_name: 'sql-expert' } }), 'sql-expert')
  assert.equal(toolStatusKey({ tool_name: 'mcp__srv__op__1', status: 'unknown' }), 'tool_status_unknown')
  assert.equal(toolStatusKey({ tool_name: 'mcp__srv__op__1', status: 'success', mcp_run: { status: 'UNKNOWN', dispatch_uncertain: true } }), 'tool_status_unknown')

  // MCP toolResultPresentation extracts safe text, structured_content, and retained artifacts for FINISHED
  const envelope = {
    ok: true,
    untrusted_mcp_output: true,
    trust_boundary: 'untrusted_external_mcp_tool_output',
    server_id: 'srv1',
    server_name: 'Analytics MCP',
    tool_name: 'render_chart',
    namespaced_name: 'mcp__srv1__render_chart__1234',
    is_error: false,
    text: 'Chart generated.',
    structured_content: { rows: 42 },
    artifacts: [{ name: '01_chart.png', path: 'outputs/mcp/job_1/01_chart.png', mime_type: 'image/png', byte_size: 128, sha256: 'abc', kind: 'image' }],
    truncated: false,
  }
  const pres = toolResultPresentation({
    tool_name: 'mcp__srv1__render_chart__1234',
    status: 'success',
    mcp_run: { status: 'FINISHED', server_id: 'srv1', server_name: 'Analytics MCP', tool_name: 'render_chart' },
  }, JSON.stringify(envelope))
  assert.equal(pres.text, 'Chart generated.')
  assert.equal(pres.mcp.status, 'success')
  assert.equal(pres.mcp.server_name, 'Analytics MCP')
  assert.deepEqual(pres.mcp.structured_content, { rows: 42 })
  assert.equal(pres.mcp.artifacts.length, 1)
  assert.equal(pres.mcp.artifacts[0].path, 'outputs/mcp/job_1/01_chart.png')
})

test('toolResultPresentation maps ADMITTED/DISPATCHING/CANCELLED/FAILED/UNKNOWN explicitly and preserves MCP summary on truncated JSON', async () => {
  const { toolResultPresentation, toolStatusKey } = await import('../src/utils/taskAgentTimeline.js')

  // ADMITTED without text must not default to completed/success
  const admittedEntry = {
    tool_name: 'mcp__srv1__query__1111',
    status: 'pending',
    mcp_run: { status: 'ADMITTED', server_id: 'srv1', server_name: 'DB MCP', tool_name: 'query', artifacts: [] },
  }
  assert.equal(toolStatusKey(admittedEntry), 'tool_status_pending')
  assert.equal(toolResultPresentation(admittedEntry, '').mcp.status, 'pending')

  // DISPATCHING without text maps to running
  const dispatchingEntry = {
    tool_name: 'mcp__srv1__query__1111',
    status: 'running',
    mcp_run: { status: 'DISPATCHING', server_id: 'srv1', server_name: 'DB MCP', tool_name: 'query', artifacts: [] },
  }
  assert.equal(toolStatusKey(dispatchingEntry), 'tool_status_running')
  assert.equal(toolResultPresentation(dispatchingEntry, '').mcp.status, 'running')

  // CANCELLED before dispatch maps to cancelled with diagnostic
  const cancelledEntry = {
    tool_name: 'mcp__srv1__query__1111',
    status: 'cancelled',
    mcp_run: {
      status: 'CANCELLED',
      server_id: 'srv1',
      server_name: 'DB MCP',
      tool_name: 'query',
      error_code: 'cancelled_before_dispatch',
      unknown_reason: 'Canceled before remote dispatch.',
      artifacts: [],
    },
  }
  assert.equal(toolStatusKey(cancelledEntry), 'tool_status_cancelled')
  const cancelledPres = toolResultPresentation(cancelledEntry, '')
  assert.equal(cancelledPres.mcp.status, 'cancelled')
  assert.equal(cancelledPres.mcp.is_error, true)
  assert.equal(cancelledPres.mcp.error_code, 'cancelled_before_dispatch')

  // Truncated / unparseable JSON receipt still retains durable mcp_run status, diagnostic, and artifacts
  const truncatedEntry = {
    tool_name: 'mcp__srv1__render__1111',
    status: 'unknown',
    result: { truncated: true },
    mcp_run: {
      status: 'UNKNOWN',
      dispatch_uncertain: true,
      server_id: 'srv1',
      server_name: 'DB MCP',
      tool_name: 'render',
      unknown_code: 'timeout',
      unknown_reason: 'Timed out after dispatch.',
      artifacts: [{ name: '01_out.png', path: 'outputs/mcp/j1/01_out.png', mime_type: 'image/png', byte_size: 64 }],
    },
  }
  const truncatedPres = toolResultPresentation(truncatedEntry, '{"untrusted_mcp_output":true,"text":"partial truncated...')
  assert.equal(truncatedPres.mcp.status, 'unknown')
  assert.equal(truncatedPres.mcp.error_code, 'timeout')
  assert.equal(truncatedPres.mcp.error_message, 'Timed out after dispatch.')
  assert.equal(truncatedPres.mcp.artifacts.length, 1)
  assert.equal(truncatedPres.mcp.truncated, true)
})

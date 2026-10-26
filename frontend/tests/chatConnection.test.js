import test from 'node:test'
import assert from 'node:assert/strict'
import { createChatConnection, replaceChatMessage, terminalChatMessage } from '../src/utils/chatConnection.js'

function fixture() {
  const timers = new Map(), sockets = [], received = [], failures = []
  let nextTimer = 0
  class Socket {
    sent = []
    constructor(url) { this.url = url; sockets.push(this) }
    send(payload) { this.sent.push(payload) }
    close() { this.closed = true; this.onclose?.() }
  }
  const connection = createChatConnection({ url: 'ws://test', payload: { ai_message_mid: 'attempt' },
    WebSocketClass: Socket, setTimer: (fn, ms) => { timers.set(++nextTimer, { fn, ms }); return nextTimer },
    clearTimer: id => timers.delete(id), onData: value => received.push(value), onFailure: code => failures.push(code),
  })
  return { connection, sockets, timers, received, failures, socket: sockets[0],
    timeout: () => [...timers.values()][0].fn() }
}

test('one socket sends once, resets idle deadline on chunks, and terminal data ends all callbacks', () => {
  const f = fixture()
  assert.equal([...f.timers.values()][0].ms, 15000)
  f.socket.onopen()
  f.socket.onopen()
  assert.equal(f.sockets.length, 1)
  assert.equal(f.socket.sent.length, 1)
  assert.equal([...f.timers.values()][0].ms, 180000)
  const previousTimer = [...f.timers.keys()][0]
  f.socket.onmessage({ data: JSON.stringify({ content: 'partial' }) })
  assert.notEqual([...f.timers.keys()][0], previousTimer)
  const staleMessage = f.socket.onmessage
  f.socket.onmessage({ data: JSON.stringify({ end: true, status: 'F', content: 'partial', error: { message: 'failed' } }) })
  assert.equal(f.received.length, 2)
  assert.equal(f.timers.size, 0)
  assert.equal(f.socket.closed, true)
  staleMessage({ data: '{"content":"late"}' })
  assert.equal(f.received.length, 2)
  assert.deepEqual(f.failures, [])
})

test('open, idle, connection and malformed-stream failures finalize once without reconnecting', () => {
  for (const mode of ['openTimeout', 'idleTimeout', 'openError', 'close', 'malformed']) {
    const f = fixture()
    if (['idleTimeout', 'close', 'malformed'].includes(mode)) f.socket.onopen()
    const staleError = f.socket.onerror
    if (mode.endsWith('Timeout')) f.timeout()
    else if (mode === 'openError') f.socket.onerror()
    else if (mode === 'close') f.socket.onclose()
    else f.socket.onmessage({ data: 'bad json' })
    staleError()
    assert.equal(f.failures.length, 1)
    assert.equal(f.failures[0], mode.endsWith('Timeout') ? 'CHAT_TIMEOUT'
      : mode === 'openError' ? 'CHAT_CONNECTION_FAILED' : 'CHAT_CONNECTION_CLOSED')
    assert.equal(f.timers.size, 0)
    assert.equal(f.sockets.length, 1)
  }
})

test('route cancellation closes connection and timers without reporting a second failure', () => {
  const f = fixture()
  const staleOpen = f.socket.onopen, staleMessage = f.socket.onmessage
  f.connection.cancel()
  staleOpen()
  staleMessage({ data: '{"end":true}' })
  assert.equal(f.socket.sent.length, 0)
  assert.equal(f.received.length, 0)
  assert.equal(f.timers.size, 0)
  assert.deepEqual(f.failures, [])
})

test('foreign terminal frames are ignored before closing and invalid JSON values finalize safely', () => {
  const f = fixture()
  f.socket.onopen()
  f.socket.onmessage({ data: '{"end":true,"mid":"other"}' })
  assert.equal(f.received.length, 0)
  assert.notEqual(f.socket.closed, true)
  assert.equal(f.timers.size, 1)
  f.socket.onmessage({ data: '{"end":true,"mid":"attempt","status":"S"}' })
  assert.equal(f.received.length, 1)
  for (const invalid of ['null', 'false', '1', '"text"', '[]']) {
    const bad = fixture()
    bad.socket.onmessage({ data: invalid })
    assert.deepEqual(bad.failures, ['CHAT_CONNECTION_CLOSED'])
    assert.equal(bad.timers.size, 0)
  }
})

test('terminal snapshots preserve partials, suppress failed workflow actions, and replace older regeneration by mid', () => {
  const pending = { mid: 'regenerated', status: 'G', content_type: 'WKF', loading: true,
    metadata: { selected_workflow: { wid: 'unsafe' } }, content: { text: 'partial', reasoning_content: 'thinking' } }
  const failed = terminalChatMessage(pending, { status: 'F', error: { message: 'failed' } })
  assert.equal(failed.content_type, 'TXT')
  assert.equal(failed.content.text, 'partial')
  assert.equal(failed.content.reasoning_content, 'thinking')
  assert.equal(failed.loading, false)
  assert.deepEqual(failed.metadata.selected_workflow, {})
  const groups = [[{ mid: 'old' }, pending], [{ mid: 'last' }]]
  assert.equal(replaceChatMessage(groups, 'regenerated', failed), true)
  assert.equal(groups[0][1], failed)
  assert.equal(groups[1][0].mid, 'last')
  const waiting = terminalChatMessage(pending, { status: 'W', selected_workflow: { wid: 'valid' } })
  assert.equal(waiting.workflow_invoke_step, 'wait_for_invoke')
  assert.equal(waiting.metadata.selected_workflow.wid, 'valid')
  assert.equal(replaceChatMessage(groups, 'absent', waiting), false)
})

export function createChatConnection({ url, payload, onData, onFailure,
  WebSocketClass = globalThis.WebSocket, setTimer = setTimeout, clearTimer = clearTimeout,
  openTimeout = 15000, idleTimeout = 180000, stopTimeout = 10000 }) {
  let socket, timer, finished = false, opened = false, stopRequested = false
  const stop = () => {
    finished = true
    clearTimer(timer)
    if (socket) {
      socket.onopen = socket.onmessage = socket.onerror = socket.onclose = null
      socket.close()
    }
  }
  const fail = code => {
    if (finished) return
    stop()
    onFailure(code)
  }
  const arm = duration => {
    clearTimer(timer)
    timer = setTimer(() => fail('CHAT_TIMEOUT'), duration)
  }
  const sendStop = () => {
    arm(stopTimeout)
    try { socket.send(JSON.stringify({ action: 'stop', mid: payload.ai_message_mid })) }
    catch { fail('CHAT_CONNECTION_CLOSED') }
  }
  const requestStop = () => {
    if (finished || stopRequested) return
    stopRequested = true
    if (opened) sendStop()
    else fail('CHAT_CONNECTION_CLOSED')
  }
  arm(openTimeout)
  try {
    socket = new WebSocketClass(url)
    socket.onopen = () => {
      if (finished || opened) return
      opened = true
      arm(idleTimeout)
      try { socket.send(JSON.stringify(payload)) } catch { fail('CHAT_CONNECTION_FAILED') }
    }
    socket.onmessage = event => {
      if (finished) return
      let data
      try { data = JSON.parse(event.data) } catch { fail('CHAT_CONNECTION_CLOSED'); return }
      if (!data || typeof data !== 'object' || Array.isArray(data)) { fail('CHAT_CONNECTION_CLOSED'); return }
      if (data.mid && payload.ai_message_mid && data.mid !== payload.ai_message_mid) return
      if (data.end) stop()
      else if (!stopRequested) arm(idleTimeout)
      onData(data)
    }
    socket.onerror = () => fail(opened ? 'CHAT_CONNECTION_CLOSED' : 'CHAT_CONNECTION_FAILED')
    socket.onclose = () => fail(opened ? 'CHAT_CONNECTION_CLOSED' : 'CHAT_CONNECTION_FAILED')
  } catch { fail('CHAT_CONNECTION_FAILED') }
  return { cancel: stop, requestStop }
}

export function replaceChatMessage(groups, mid, snapshot) {
  for (const group of groups) {
    const index = group.findIndex(message => message.mid === mid)
    if (index !== -1) {
      group.splice(index, 1, snapshot)
      return true
    }
  }
  return false
}

export function terminalChatMessage(current, data) {
  const status = data.status || (current.content_type === 'WKF' ? 'W' : 'S')
  const failed = status === 'F'
  const stopped = status === 'C'
  const workflow = !failed && !stopped && status === 'W'
  const metadata = { ...current.metadata,
    ...(data.model ? { model: data.model } : {}),
    ...(failed ? { selected_workflow: {}, error: data.error } : {}),
    ...(!failed && !stopped && data.selected_workflow ? { selected_workflow: data.selected_workflow } : {}),
  }
  if (stopped) {
    metadata.selected_workflow = {}
    delete metadata.error
    delete metadata.tool_calls
    delete metadata.tools
  }
  return {
    ...JSON.parse(JSON.stringify(current)), loading: false, status,
    content_type: workflow ? 'WKF' : 'TXT',
    workflow_invoke_step: workflow ? 'wait_for_invoke' : '',
    metadata,
    content: { ...current.content, text: data.content ?? current.content.text,
      reasoning_content: data.reasoning_content ?? current.content.reasoning_content },
  }
}

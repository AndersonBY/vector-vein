import { iconButtonFixture } from './taskAgentButtonFixture.js'
import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick, reactive } from 'vue'
import { createI18n } from 'vue-i18n'
import { createServer } from 'vite'
import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

const flush = async () => {
  for (let i = 0; i < 6; i++) await new Promise(resolve => setImmediate(resolve))
  await nextTick()
}
const deferred = () => {
  let resolve
  const promise = new Promise(yes => {
    resolve = yes
  })
  return { promise, resolve }
}

const VER_A = 'a'.repeat(64)
const VER_B = 'b'.repeat(64)

async function componentSource(path, id) {
  const filename = fileURLToPath(new URL(path, import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const script = compileScript(descriptor, { id })
  const source = script.content.replace('export default', 'const component =')
  const template = compileTemplate({
    source: descriptor.template.content,
    filename,
    id,
    compilerOptions: { bindingMetadata: script.bindings },
  }).code.replace('export function render', 'function render')
  return `${source}\n${template}\ncomponent.render = render; export default component`
}

const createTreeRenderer = () =>
  createRenderer({
    patchProp: (node, key, _old, value) => {
      node.props[key] = value
    },
    insert: (node, parent, anchor) => {
      if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
      node.parent = parent
      const index = anchor ? parent.children.indexOf(anchor) : -1
      if (index < 0) parent.children.push(node)
      else parent.children.splice(index, 0, node)
    },
    remove: node => {
      if (node?.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
    },
    createElement: type => ({ type, props: {}, children: [], parent: null }),
    createText: text => ({ text }),
    createComment: text => ({ text }),
    setText: (node, text) => {
      node.text = text
    },
    setElementText: (node, text) => {
      node.text = text
    },
    parentNode: node => node.parent,
    nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
  })

const textOf = node => [node?.text || '', ...(node?.children || []).map(textOf)].join(' ')

async function withContextUsage(run, initialProps = {}) {
  const previous = globalThis.__ctxUsageTest
  const timers = new Map()
  let nextTimerId = 1
  const realSetTimeout = globalThis.setTimeout
  const realClearTimeout = globalThis.clearTimeout

  globalThis.setTimeout = (fn, delay) => {
    if (delay === 3000) {
      const id = nextTimerId++
      timers.set(id, fn)
      return id
    }
    return realSetTimeout(fn, delay)
  }
  globalThis.clearTimeout = id => {
    if (timers.has(id)) {
      timers.delete(id)
      return
    }
    realClearTimeout(id)
  }

  const state = {
    props: reactive({
      taskId: 'task_ctx_1',
      tokenUsage: null,
      contextWindow: null,
      disabled: false,
      ...initialProps,
    }),
    calls: [],
    refreshes: 0,
    timers,
    runNextPoll: async () => {
      const first = timers.entries().next().value
      if (!first) return false
      const [id, fn] = first
      timers.delete(id)
      fn()
      await flush()
      return true
    },
    request: async () => ({ status: 200, data: {} }),
  }
  globalThis.__ctxUsageTest = state

  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    '@/icons': 'export const Refresh={render:()=>null},OffScreenOne=Refresh',
    '/context-usage-test.js': await componentSource('../src/views/Workspace/TaskAgent/TaskAgentContextUsage.vue', 'ctx-usage'),
    '@/api/taskAgent': 'export const taskAgentAPI=(a,p={})=>{const s=globalThis.__ctxUsageTest;s.calls.push({action:a,payload:JSON.parse(JSON.stringify(p))});return s.request(a,p)}',
  }

  const server = await createServer({
    configFile: false,
    root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [
      {
        name: 'ctx-usage-fixture',
        resolveId: id => (Object.hasOwn(modules, id) ? id : undefined),
        load: id => modules[id],
      },
    ],
    server: { middlewareMode: true, hmr: false, ws: false },
    optimizeDeps: { noDiscovery: true },
    appType: 'custom',
  })

  let app
  let vm
  const root = { type: 'root', props: {}, children: [], parent: null }
  try {
    const Component = (await server.ssrLoadModule('/context-usage-test.js')).default
    const renderer = createTreeRenderer()
    const Host = {
      setup() {
        return () =>
          h(Component, {
            ref: instance => {
              if (instance) vm = instance
            },
            taskId: state.props.taskId,
            tokenUsage: state.props.tokenUsage,
            contextWindow: state.props.contextWindow,
            disabled: state.props.disabled,
            onRefresh: () => {
              state.refreshes++
            },
          })
      },
    }
    app = renderer.createApp(Host)
    app.component('APopover', {
      props: ['open'],
      emits: ['update:open'],
      setup(props, { slots }) {
        return () => h('div', { class: 'a-popover-stub', open: props.open }, [slots.default?.(), slots.content?.()])
      },
    })
    app.component('AButton', {
      props: ['type', 'size', 'disabled', 'loading'],
      setup(props, { slots, attrs }) {
        return () => h('button', { ...props, ...attrs }, slots.default?.())
      },
    })
    app.component('AProgress', {
      props: ['type', 'size', 'strokeWidth', 'percent', 'showInfo'],
      setup(props) {
        return () => h('div', { class: 'a-progress-stub', percent: props.percent })
      },
    })
    const messages = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
    app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } }))
    app.mount(root)
    await flush()
    await run(vm, state, root)
  } finally {
    app?.unmount()
    await server.close()
    globalThis.setTimeout = realSetTimeout
    globalThis.clearTimeout = realClearTimeout
    globalThis.__ctxUsageTest = previous
  }
}

test('TaskAgentContextUsage does not fetch on mount, initializes honestly from latest_input_tokens, clamps percent at 100 and reports unknown/partial cache rates without NaN', async () => {
  await withContextUsage(async (vm, state, root) => {
    // 1. No API call on mount, unknown counts display '—' without inventing 0
    assert.equal(state.calls.length, 0)
    assert.equal(vm.usedTokens, null)
    assert.equal(vm.contextPercent, null)
    assert.equal(vm.cacheHitRate, '—')
    assert.match(textOf(root), /暂无使用数据/)

    // 2. Props provide latest_input_tokens and contextWindow: shows 'last request' source and clamps ring at 100 while preserving actual counts
    state.props.tokenUsage = {
      input_tokens: 150000,
      output_tokens: 4000,
      latest_input_tokens: 150000,
      cache_read_tokens: 45000,
      cache_input_tokens: 100000,
      reported_calls: 2,
      cache_missing_calls: 1,
    }
    state.props.contextWindow = 128000
    await flush()
    assert.equal(vm.usedTokens, 150000)
    assert.equal(vm.totalWindow, 128000)
    assert.equal(vm.contextPercent, 117)
    assert.equal(vm.clampedPercent, 100)
    assert.equal(vm.sourceNote, '最近请求（含缓存）')
    assert.equal(vm.cacheHitRate, '45%')
    assert.equal(vm.cacheMissingCalls, 1)
    assert.match(textOf(root), /部分请求未返回缓存数据/)

    // 3. Zero/invalid cache_input_tokens or reported_calls=0 never produces NaN
    state.props.tokenUsage = {
      latest_input_tokens: 2000,
      cache_read_tokens: 0,
      cache_input_tokens: 0,
      reported_calls: 0,
      cache_missing_calls: 0,
    }
    state.props.contextWindow = 0
    await flush()
    assert.equal(vm.contextPercent, null)
    assert.equal(vm.clampedPercent, null)
    assert.equal(vm.cacheHitRate, '—')
  })
})

test('TaskAgentContextUsage fetches on open, prefers native estimates and limits, polls every 3s while open, and preserves last good data on 503 failure', async () => {
  await withContextUsage(
    async (vm, state, root) => {
      state.request = async action => {
        if (action === 'task_context') {
          return {
            status: 200,
            data: {
              context: {
                contextVersion: VER_A,
                estimates: { total: 32000 },
                limits: { contextWindow: 128000, compactionThreshold: 100000 },
                lastCompaction: null,
              },
              token_usage: {
                input_tokens: 60000,
                output_tokens: 2000,
                latest_input_tokens: 28000,
                cache_read_tokens: 30000,
                cache_input_tokens: 60000,
                reported_calls: 3,
                cache_missing_calls: 0,
              },
              compaction: null,
            },
          }
        }
        return { status: 200, data: {} }
      }

      // Open popover triggers fetchContext and schedules 3s poll
      vm.open = true
      await flush()
      assert.equal(state.calls.length, 1)
      assert.deepEqual(state.calls[0], { action: 'task_context', payload: { task_id: 'task_ctx_1' } })
      assert.equal(vm.usedTokens, 32000)
      assert.equal(vm.totalWindow, 128000)
      assert.equal(vm.compactionThreshold, 100000)
      assert.equal(vm.contextPercent, 25)
      assert.equal(vm.sourceNote, '当前上下文估算')
      assert.equal(vm.cacheHitRate, '50%')
      assert.equal(state.timers.size, 1)

      // Next poll fails with 503: last good data is preserved and loadFailed surfaces Retry
      state.request = async () => ({ status: 503, data: {} })
      await state.runNextPoll()
      assert.equal(vm.loadFailed, true)
      assert.equal(vm.usedTokens, 32000)
      assert.equal(vm.totalWindow, 128000)
      assert.equal(vm.cacheHitRate, '50%')
      assert.match(textOf(root), /无法读取上下文使用情况，请重试。/)

      // Closing popover stops polling when no compaction is pending
      vm.open = false
      await flush()
      assert.equal(state.timers.size, 0)
      // Subsequent task polling replaces a stale popup estimate without background RPCs.
      state.props.tokenUsage = { latest_input_tokens: 42000, reported_calls: 4, cache_read_tokens: 40000, cache_input_tokens: 80000 }
      state.props.contextWindow = 200000
      await flush()
      assert.equal(vm.usedTokens, 42000)
      assert.equal(vm.totalWindow, 200000)
      assert.equal(vm.contextPercent, 21)
      assert.equal(vm.sourceNote, '最近请求（含缓存）')
      assert.equal(state.timers.size, 0)
    },
    {
      tokenUsage: { latest_input_tokens: 10000, cache_read_tokens: 0, cache_input_tokens: 0, reported_calls: 0, cache_missing_calls: 0 },
      contextWindow: 64000,
    },
  )
})

test('TaskAgentContextUsage handles manual compaction queued -> running -> completed, keeps polling when closed until terminal, and respects disabled prop', async () => {
  await withContextUsage(async (vm, state) => {
    let serverCompaction = null
    let estimateTotal = 90000
    state.request = async (action, payload) => {
      if (action === 'task_context') {
        return {
          status: 200,
          data: {
            context: {
              contextVersion: VER_A,
              estimates: { total: estimateTotal },
              limits: { contextWindow: 100000, compactionThreshold: 80000 },
              lastCompaction: null,
            },
            token_usage: { latest_input_tokens: 90000, cache_read_tokens: 10000, cache_input_tokens: 50000, reported_calls: 1, cache_missing_calls: 0 },
            compaction: serverCompaction,
          },
        }
      }
      if (action === 'compact_context') {
        serverCompaction = { request_id: 'req_compact_1', status: 'queued' }
        return {
          status: 200,
          data: {
            compaction: {
              accepted: true,
              requestId: 'req_compact_1',
              actionId: payload.action_id,
            },
          },
        }
      }
      return { status: 200, data: {} }
    }

    vm.open = true
    await flush()
    assert.equal(vm.canCompact, true)

    // Parent busy (disabled=true) disables compaction while still allowing reading usage
    state.props.disabled = true
    await flush()
    assert.equal(vm.canCompact, false)
    state.props.disabled = false
    await flush()
    assert.equal(vm.canCompact, true)

    // Trigger compaction -> accepted means queued, not completed; emits refresh
    await vm.requestCompact()
    const compactCall = state.calls.find(c => c.action === 'compact_context')
    assert.ok(compactCall)
    assert.equal(compactCall.payload.task_id, 'task_ctx_1')
    assert.equal(compactCall.payload.expected_context_version, VER_A)
    assert.match(compactCall.payload.action_id, /^[0-9a-f]{32}$/i)
    assert.equal(vm.compactionState, 'queued')
    assert.equal(vm.canCompact, false, 'Competing compaction must be disabled while queued')
    assert.equal(state.refreshes, 1)

    // Close popover while queued: polling continues until terminal
    vm.open = false
    await flush()
    assert.equal(state.timers.size, 1, 'Polling must continue while compaction is pending even when popover is closed')

    // Poll transitions to running
    serverCompaction = { request_id: 'req_compact_1', status: 'running' }
    await state.runNextPoll()
    assert.equal(vm.compactionState, 'running')
    assert.equal(state.timers.size, 1)

    // Poll transitions to completed: emits refresh and stops background polling since popover is closed
    serverCompaction = { request_id: 'req_compact_1', status: 'completed' }
    estimateTotal = 42000
    await state.runNextPoll()
    assert.equal(vm.compactionState, 'completed')
    assert.equal(vm.usedTokens, 42000)
    assert.equal(state.refreshes, 2)
    assert.equal(state.timers.size, 0, 'Polling must stop once compaction reaches terminal state and popover is closed')
  })
})

test('TaskAgentContextUsage preserves exact action_id and expected_context_version on 503 uncertain retry, and clears attempt on 409 context_changed', async () => {
  await withContextUsage(async (vm, state) => {
    let currentVer = VER_A
    let compactStatus = 503
    let compactData = {}

    state.request = async action => {
      if (action === 'task_context') {
        return {
          status: 200,
          data: {
            context: {
              contextVersion: currentVer,
              estimates: { total: 50000 },
              limits: { contextWindow: 100000, compactionThreshold: 80000 },
              lastCompaction: null,
            },
            token_usage: { latest_input_tokens: 50000, cache_read_tokens: 0, cache_input_tokens: 0, reported_calls: 0, cache_missing_calls: 0 },
            compaction: null,
          },
        }
      }
      if (action === 'compact_context') {
        return { status: compactStatus, data: compactData }
      }
      return { status: 200, data: {} }
    }

    vm.open = true
    await flush()

    // 1. 503 uncertain failure preserves exact action_id + expected_context_version
    await vm.requestCompact()
    assert.equal(vm.compactionState, 'uncertain')
    assert.ok(vm.pendingAttempt)
    const firstCompactPayload = state.calls.filter(c => c.action === 'compact_context')[0].payload

    // Even if contextVersion updates in background before user retries, retry of uncertain attempt reuses exact identity
    currentVer = VER_B
    compactStatus = 409
    compactData = { context_error: 'context_changed' }
    await vm.requestCompact()
    const secondCompactPayload = state.calls.filter(c => c.action === 'compact_context')[1].payload
    assert.deepEqual(secondCompactPayload, firstCompactPayload, 'Uncertain retry must reuse exact action_id and expected_context_version')

    // 2. 409 context_changed clears pendingAttempt, refreshes context to VER_B, and shows changed status
    assert.equal(vm.compactionState, 'changed')
    assert.equal(vm.pendingAttempt, null)
    assert.equal(vm.contextData.contextVersion, VER_B)

    // 3. Subsequent deliberate compact uses new action_id and new VER_B
    compactStatus = 200
    compactData = { compaction: { accepted: true, requestId: 'req_after_409' } }
    await vm.requestCompact()
    const thirdCompactPayload = state.calls.filter(c => c.action === 'compact_context')[2].payload
    assert.notEqual(thirdCompactPayload.action_id, firstCompactPayload.action_id)
    assert.equal(thirdCompactPayload.expected_context_version, VER_B)
    assert.equal(vm.compactionState, 'queued')
  })
})

test('TaskAgentContextUsage ignores stale responses across taskId switches and cleans up timers on unmount', async () => {
  let activeTimersRef
  await withContextUsage(async (vm, state) => {
    activeTimersRef = state.timers
    const slowTask1 = deferred()

    state.request = async (action, payload) => {
      if (action === 'task_context' && payload.task_id === 'task_ctx_1') {
        return slowTask1.promise
      }
      return {
        status: 200,
        data: {
          context: {
            contextVersion: VER_B,
            estimates: { total: 12000 },
            limits: { contextWindow: 64000, compactionThreshold: 50000 },
            lastCompaction: null,
          },
          token_usage: { latest_input_tokens: 12000, cache_read_tokens: 6000, cache_input_tokens: 12000, reported_calls: 1, cache_missing_calls: 0 },
          compaction: null,
        },
      }
    }

    vm.open = true
    await flush()

    // Switch taskId while task_ctx_1 request is in flight
    state.props.taskId = 'task_ctx_2'
    await flush()
    assert.equal(vm.usedTokens, 12000)

    // Resolve stale task_ctx_1 response: must be ignored
    slowTask1.resolve({
      status: 200,
      data: {
        context: {
          contextVersion: VER_A,
          estimates: { total: 99999 },
          limits: { contextWindow: 128000, compactionThreshold: 100000 },
          lastCompaction: null,
        },
      },
    })
    await flush()
    assert.equal(vm.usedTokens, 12000)
    assert.equal(vm.contextData.contextVersion, VER_B)
    assert.equal(state.timers.size, 1)
  })
  assert.equal(activeTimersRef.size, 0, 'Unmounting component must clear all poll timers')
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createSSRApp, createRenderer, h, nextTick, reactive, ssrContextKey } from 'vue'
import { createPinia } from 'pinia'
import { renderToString } from 'vue/server-renderer'
import { createI18n } from 'vue-i18n'
import { createServer } from 'vite'
import vue from '@vitejs/plugin-vue'

const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); await nextTick() }
const assistant = (mid, status = 'S') => ({ mid, author_type: 'A', status, content_type: 'TXT',
  create_time: 1, metadata: {}, content: { text: 'previous', reasoning_content: '' } })

test('actual chat components preserve drafts, finalize failed attempts, target regeneration and render safe retryable history', async () => {
  const previousWindow = globalThis.window, previousSocket = globalThis.WebSocket
  const previousHarness = globalThis.__chatFailureHarness
  const storageDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: { getItem: () => null } })
  const sockets = [], calls = [], errors = []
  let request = async () => ({ status: 500 })
  class Socket {
    sent = []
    constructor() { sockets.push(this) }
    send(value) { this.sent.push(value) }
    close() { this.closed = true }
    chunk(data) { this.onmessage?.({ data: JSON.stringify(data) }) }
  }
  globalThis.WebSocket = Socket
  globalThis.window = { innerWidth: 1000, addEventListener() {}, removeEventListener() {}, pywebview: { api: new Proxy({}, {
    get: (_, action) => async payload => { calls.push({ action, payload }); return request(action, payload) },
  }) } }
  globalThis.__chatFailureHarness = { route: reactive({ params: { conversationId: 'cid', agentId: 'agent' }, query: {} }),
    router: { push: async () => {}, replace: async () => {} }, errors }
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [vue(), { name: 'chat-ui-fixtures', enforce: 'pre',
    transform(source, id) {
      if (!id.endsWith('.vue')) return
      return source.replace(/from (['"])vue-router\1/g, 'from "virtual:chat-router"')
        .replace(/from (['"])ant-design-vue\1/g, 'from "virtual:chat-ant"')
        .replace(/from (['"])@\/utils\/util\1/g, 'from "virtual:chat-util"')
        .replace(/from (['"])@\/utils\/common\1/g, 'from "virtual:chat-common"')
        .replace(/from (['"])@\/components\/[^'"]+\.vue\1/g, 'from "virtual:chat-child:stub"')
    }, resolveId(id) {
      if (id.startsWith('virtual:chat-')) return '\0' + id.slice(8)

      const normalized = id.replaceAll('\\', '/')
      if (id === 'vue-router') return '\0chat-router'
      if (id === 'ant-design-vue') return '\0chat-ant'
      if (normalized.endsWith('/utils/util')) return '\0chat-util'
      if (normalized.endsWith('/utils/common')) return '\0chat-common'
      if (normalized.endsWith('.vue') && !['ConversationDetail.vue', 'ConversationNew.vue', 'ChatMessage.vue'].some(name => normalized.endsWith(name))) return `\0chat-child:${normalized}`
    }, load(id) {
      if (id === '\0chat-router') return 'export const useRoute = () => globalThis.__chatFailureHarness.route; export const useRouter = () => globalThis.__chatFailureHarness.router'
      if (id === '\0chat-ant') return 'export const message = { error: value => globalThis.__chatFailureHarness.errors.push(value), success() {} }; export const theme = { useToken: () => ({ token: { value: { colorPrimary: "#1677ff", colorPrimaryBg: "#e6f4ff" } } }) }'
      if (id === '\0chat-util') return 'export const navigateToElementBottom = () => {}'
      if (id === '\0chat-common') return 'export const defaultSettings = { en: {}, "en-US": {} }'
      if (id.startsWith('\0chat-child:')) return 'import {h} from "vue"; export default {props:["text"],setup: p => () => h("div",p.text || "")}'
    } }],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)), 'vue-router': '\0chat-router', 'ant-design-vue': '\0chat-ant' } },
    server: { middlewareMode: true, hmr: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  try {
    const locale = JSON.parse(await readFile(new URL('../src/locales/en-US.json', import.meta.url), 'utf8'))
    const render = async (path, props, exercise) => {
      const component = (await server.ssrLoadModule(path)).default
      const app = createSSRApp({ ...component, async setup(props, context) {
        const bindings = component.setup(props, context)
        await exercise(bindings)
        return bindings
      } }, props)
      app.use(createPinia())
      app.use(createI18n({ legacy: false, locale: 'en-US', messages: { 'en-US': locale } }))
      for (const name of ['AFlex', 'ATypographyTitle', 'ATypographyText', 'ATypographyParagraph', 'ASpin', 'ATooltip',
        'AAvatar', 'AAlert', 'ATextarea', 'ACollapse', 'ACollapsePanel', 'APopconfirm', 'AButton', 'ASpace']) {
        app.component(name, { setup: (_, { slots }) => () => h(name === 'AButton' ? 'button' : 'div', slots.default?.()) })
      }
      return renderToString(app)
    }
    const detail = '/src/views/Workspace/Chat/ConversationDetail.vue'
    const prepare = c => {
      c.conversation.value = { cid: 'cid', agent: { name: 'AI' }, settings: {}, related_workflows: [], related_templates: [] }
      c.userChatsStore.addConversation(c.conversation.value)
    }
    const navigations = []
    globalThis.__chatFailureHarness.router.push = async location => { navigations.push(location) }
    await render(detail, {}, async c => {
      prepare(c)
      c.conversation.value.title = 'original'
      c.userInput.value = 'unsent draft'
      c.attachments.value = ['local-file']
      c.messages.value = [[assistant('saved')]]
      const pending = deferred()
      request = (action, payload) => {
        assert.equal(action, 'conversation__fork')
        assert.deepEqual(payload, { source_cid: 'cid', source_mid: 'saved', title: 'original · Fork' })
        return pending.promise
      }
      const fork = c.forkConversation('saved')
      assert.equal(c.forking.value, true)
      assert.equal(c.canFork.value, false)
      const count = calls.length
      await c.forkConversation('saved')
      assert.equal(await c.sendMessage('blocked during fork'), false)
      await c.regenerate('saved', 0)
      assert.equal(calls.length, count)
      pending.resolve({ status: 200, data: { cid: 'forked' } })
      await fork
      assert.deepEqual(navigations.at(-1), { name: 'conversationDetail', params: { agentId: 'agent', conversationId: 'forked' } })
      assert.equal(c.forking.value, false)
      assert.equal(c.userInput.value, 'unsent draft')
      assert.deepEqual(c.attachments.value, ['local-file'])
      assert.equal(c.conversation.value.cid, 'cid')
      assert.equal(c.messages.value[0][0].mid, 'saved')
    })
    for (const response of [{ status: 500 }, { status: 200, data: {} },
      { status: 409, code: 'CONVERSATION_BUSY' }, new Error('connection')]) {
      await render(detail, {}, async c => {
        prepare(c)
        c.messages.value = [[assistant('saved')]]
        const count = navigations.length, errorCount = errors.length
        c.userInput.value = 'keep draft'
        request = async () => { if (response instanceof Error) throw response; return response }
        await c.forkConversation('saved')
        assert.equal(c.forking.value, false)
        assert.equal(c.canFork.value, true)
        assert.equal(navigations.length, count)
        assert.equal(errors.length, errorCount + 1)
        assert.equal(c.userInput.value, 'keep draft')
      })
    }
    await render(detail, {}, async c => {
      prepare(c)
      const count = calls.length
      c.conversation.value.cid = 'not-the-loaded-conversation'
      assert.equal(c.canFork.value, false)
      await c.forkConversation('saved')
      c.conversation.value.cid = 'cid'
      for (const field of ['loading', 'sending', 'receiving']) {
        c[field].value = true
        assert.equal(c.canFork.value, false)
        await c.forkConversation('saved')
        c[field].value = false
      }
      for (const status of ['P', 'G', 'R']) {
        c.messages.value = [[assistant('busy', status)]]
        await c.forkConversation('busy')
      }
      assert.equal(calls.length, count)
      c.messages.value = [[assistant('failed', 'F')]]
      assert.equal(c.canFork.value, true)
      c.messages.value = [[{ ...assistant('user'), author_type: 'U' }]]
      await c.forkConversation('user')
      await c.forkConversation('not-in-conversation')
      assert.equal(calls.length, count)
    })
    await render(detail, {}, async c => {
      prepare(c)
      c.messages.value = [[assistant('saved')]]
      const count = navigations.length
      const pending = deferred()
      request = () => pending.promise
      const fork = c.forkConversation('saved')
      c.conversationId.value = 'other-conversation'
      pending.resolve({ status: 200, data: { cid: 'late-copy' } })
      await fork
      assert.equal(navigations.length, count)
    })
    await render(detail, {}, async c => {
      prepare(c)
      const pending = deferred()
      request = () => pending.promise
      c.userInput.value = 'keep draft'
      c.attachments.value = ['local-file']
      const send = c.sendMessage(c.userInput.value)
      const count = calls.length
      assert.equal(c.sending.value, true)
      assert.equal(await c.sendMessage('duplicate'), false)
      assert.equal(calls.length, count)
      pending.reject(new Error('network'))
      assert.equal(await send, false)
      assert.equal(c.userInput.value, 'keep draft')
      assert.deepEqual(c.attachments.value, ['local-file'])
      assert.equal(c.sending.value, false)
      assert.equal(c.messages.value.length, 0)
    })
    await render(detail, {}, async c => {
      prepare(c)
      request = async (action, payload) => action === 'message__send'
        ? { status: 200, data: { user_message_mid: 'user', ai_message_mid: 'attempt' } }
        : action === 'setting__get_port' ? { status: 200, data: { port: 9999 } }
        : { status: 200, data: { ...assistant(payload.mid), content: { text: 'already completed' } } }
      c.userInput.value = 'hello'
      assert.equal(await c.sendMessage('hello'), true)
      await flush()
      const socket = sockets.at(-1)
      socket.onopen()
      socket.chunk({ content: 'partial', reasoning_content: 'thought' })
      assert.equal(c.receiving.value, true)
      const count = calls.length
      await c.regenerate('previous', 0)
      assert.equal(calls.length, count)
      socket.onclose()
      assert.equal(c.receiving.value, false)
      assert.equal(c.messages.value[1][0].status, 'F')
      assert.equal(c.messages.value[1][0].content.text, 'partial')
      await flush()
      assert.equal(c.messages.value[1][0].status, 'S')
      assert.equal(c.messages.value[1][0].content.text, 'already completed')
      assert.equal(c.sending.value, false)
      assert.equal(socket.sent.length, 1)
    })
    await render(detail, {}, async c => {
      prepare(c)
      c.messages.value = [[assistant('old')], [assistant('last')]]
      c.messagePagination.set(1, 0)
      request = async action => action === 'message__regenerate'
        ? { status: 200, data: { ai_message_mid: 'regenerated' } }
        : action === 'setting__get_port' ? { status: 200, data: { port: 9999 } }
        : { status: 500 }
      await c.regenerate('old', 0)
      await flush()
      const socket = sockets.at(-1)
      socket.onopen()
      socket.chunk({ end: true, mid: 'regenerated', status: 'F', error: { message: '<script>failure</script>' } })
      await flush()
      assert.equal(c.messages.value[0][1].mid, 'regenerated')
      assert.equal(c.messages.value[0][1].status, 'F')
      assert.equal(c.messages.value.length, 1)
      assert.equal(c.messagePagination.has(1), false)
      assert.equal(c.messagePagination.get(0), 1)
      assert.equal(c.receiving.value, false)
    })
    await render(detail, {}, async c => {
      prepare(c)
      const pending = deferred()
      request = action => action === 'message__send' ? pending.promise : Promise.resolve({ status: 200 })
      const send = c.sendMessage('old conversation')
      c.cancelAttempt()
      c.conversationId.value = 'next-conversation'
      pending.resolve({ status: 200, data: { ai_message_mid: 'stale', user_message_mid: 'stale-user' } })
      await send
      assert.equal(c.messages.value.length, 0)
      assert.equal(c.sending.value, false)
      assert.ok(calls.some(call => call.action === 'message__fail_notice' && call.payload.mid === 'stale' && call.payload.cid === 'cid'))
    })
    await render(detail, {}, async c => {
      prepare(c)
      c.messages.value = [[assistant('original')]]
      const oldNotice = deferred()
      let generation = 0
      request = async action => action === 'message__regenerate'
        ? { status: 200, data: { ai_message_mid: `attempt-${++generation}` } }
        : action === 'setting__get_port' ? { status: 200, data: { port: 9999 } }
        : generation === 1 ? oldNotice.promise : { status: 500 }
      await c.regenerate('original', 0)
      await flush()
      sockets.at(-1).chunk({ end: true, mid: 'attempt-1', status: 'S', content: 'first reply' })
      await c.regenerate('attempt-1', 0)
      await flush()
      sockets.at(-1).chunk({ end: true, mid: 'attempt-2', status: 'F' })
      oldNotice.resolve({ status: 200, data: { ...assistant('attempt-1'), content: { text: 'stale replacement' } } })
      await flush()
      assert.equal(c.messages.value[0][1].content.text, 'first reply')
      assert.equal(c.messages.value[0][2].status, 'F')
      assert.equal(c.receiving.value, false)
    })
    for (const response of [{ status: 500 }, new Error('create failed')]) {
      await render('/src/views/Workspace/Chat/ConversationNew.vue', {}, async c => {
        request = async () => { if (response instanceof Error) throw response; return response }
        c.userInput.value = 'unsent'
        c.attachments.value = ['file']
        await c.sendMessage()
        assert.equal(c.userInput.value, 'unsent')
        assert.deepEqual(c.attachments.value, ['file'])
        assert.equal(c.sending.value, false)
        assert.equal(c.userChatsStore.unsentChats.length, 0)
      })
    }
    await render('/src/views/Workspace/Chat/ConversationNew.vue', {}, async c => {
      const pending = deferred()
      request = () => pending.promise
      c.userInput.value = 'leaving'
      const send = c.sendMessage()
      c.cancelCreate()
      pending.resolve({ status: 200, data: { cid: 'late-created' } })
      await send
      assert.equal(c.userChatsStore.unsentChats.length, 0)
      assert.equal(c.userChatsStore.conversations.length, 0)
      assert.equal(c.userInput.value, 'leaving')
      assert.equal(c.sending.value, false)
    })
    await render(detail, {}, async c => {
      prepare(c)
      c.loading.value = true
      request = async () => { throw new Error('history unavailable') }
      assert.equal(await c.fetchConversation('cid'), false)
      assert.equal(c.loading.value, false)
      const pending = deferred()
      request = () => pending.promise
      const fetch = c.fetchConversation('cid')
      c.conversationId.value = 'new-cid'
      pending.resolve({ status: 200, data: { conversation: { cid: 'cid' }, messages: [[assistant('stale')]] } })
      assert.equal(await fetch, false)
      assert.equal(c.messages.value.length, 0)
    })
    const branchResponse = (tail = 'old-tail') => ({ status: 200, data: {
      conversation: { cid: 'cid', agent: { name: 'AI' }, settings: {}, related_workflows: [], related_templates: [] },
      messages: [[assistant('root')], [assistant('old-version'), assistant('new-version')], [assistant(tail)]],
      selected_message_path: ['root', 'old-version', tail],
    } })
    await render(detail, {}, async c => {
      prepare(c)
      c.messages.value = branchResponse('new-tail').data.messages
      c.messagePagination.set(1, 1)
      c.userInput.value = 'draft stays'
      c.attachments.value = ['local-file']
      const pending = deferred(), replacements = []
      globalThis.__chatFailureHarness.route.query = { mid: 'search-target', keep: 'yes' }
      globalThis.__chatFailureHarness.router.replace = async location => { replacements.push(location) }
      request = (action, payload) => {
        assert.equal(action, 'conversation__select_branch')
        assert.deepEqual(payload, { cid: 'cid', mid: 'old-version' })
        return pending.promise
      }
      const selection = c.switchMessagePage(1, 'prev')
      assert.equal(c.loading.value, true)
      assert.equal(c.messagePagination.get(1), 1)
      const count = calls.length
      await c.switchMessagePage(1, 'prev')
      assert.equal(calls.length, count)
      pending.resolve(branchResponse())
      await selection
      assert.equal(c.messagePagination.get(1), 0)
      assert.equal(c.messages.value[2][0].mid, 'old-tail')
      assert.equal(c.loading.value, false)
      assert.equal(c.focusedMessageMid.value, '')
      assert.equal(c.userInput.value, 'draft stays')
      assert.deepEqual(c.attachments.value, ['local-file'])
      assert.deepEqual(replacements, [{ query: { keep: 'yes' } }])
      globalThis.__chatFailureHarness.route.query = {}
    })
    for (const failedSelection of [{ status: 500 }, { status: 409 }, new Error('network')]) {
      await render(detail, {}, async c => {
        prepare(c)
        c.messages.value = branchResponse('new-tail').data.messages
        c.messagePagination.set(1, 1)
        const count = errors.length
        request = async () => { if (failedSelection instanceof Error) throw failedSelection; return failedSelection }
        await c.switchMessagePage(1, 'prev')
        assert.equal(c.loading.value, false)
        assert.equal(c.messagePagination.get(1), 1)
        assert.equal(c.messages.value[2][0].mid, 'new-tail')
        assert.equal(errors.length, count + 1)
      })
    }
    await render(detail, {}, async c => {
      prepare(c)
      c.messages.value = branchResponse('new-tail').data.messages
      c.messagePagination.set(1, 1)
      const pending = deferred()
      request = () => pending.promise
      const selection = c.switchMessagePage(1, 'prev')
      c.conversationId.value = 'another-conversation'
      pending.resolve(branchResponse())
      await selection
      assert.equal(c.messages.value[2][0].mid, 'new-tail')
      assert.equal(c.messagePagination.get(1), 1)
    })
    const reopened = await render(detail, {}, async c => {
      prepare(c)
      request = async () => branchResponse()
      assert.equal(await c.fetchConversation('cid', ''), true)
      assert.equal(c.messagePagination.get(1), 0)
      assert.equal(c.focusedMessageMid.value, '')
    })
    assert.match(reopened, /data-message-mid="old-version"/)
    assert.doesNotMatch(reopened, /data-message-mid="new-version"/)
    for (const page of [undefined, 0, 1]) {
      await render(detail, {}, async c => {
        prepare(c)
        c.messages.value = [[assistant('root')], [assistant('old-version'), assistant('new-version')]]
        if (page !== undefined) c.messagePagination.set(1, page)
        request = async (action, payload) => {
          if (action === 'message__send') {
            assert.equal(payload.parent_mid, page === 0 ? 'old-version' : 'new-version')
            return { status: 200, data: { ai_message_mid: 'attempt', user_message_mid: 'question' } }
          }
          if (action === 'setting__get_port') return { status: 200, data: { port: 9999 } }
          return { status: 200 }
        }
        await c.sendMessage('continue selected')
        await flush()
        c.cancelAttempt()
      })
    }
    await render(detail, {}, async c => {
      prepare(c)
      c.messages.value = [[assistant('root')], [assistant('workflow')], [assistant('other-tail')]]
      request = async action => action === 'message__append_answer' ? { status: 200, data: { ai_message_mid: 'continued' } }
        : action === 'setting__get_port' ? { status: 200, data: { port: 9999 } } : { status: 200 }
      await c.onAppendAnswer('workflow')
      await flush()
      assert.deepEqual(c.messages.value.map(group => group[0].mid), ['root', 'workflow', 'continued'])
      c.cancelAttempt()
    })
    const focusedHistory = await render(detail, {}, async c => {
      prepare(c)
      const scrolled = []
      c.chatBodyElementRef.value = { scrollTop: 100, clientHeight: 600,
        getBoundingClientRect: () => ({ top: 50 }), scrollTo: options => scrolled.push(options),
        querySelectorAll: () => [
          { dataset: { messageMid: 'new-version' }, offsetHeight: 100, getBoundingClientRect: () => ({ top: 900 }) },
          { dataset: { messageMid: 'old-version' }, offsetHeight: 200, getBoundingClientRect: () => ({ top: 450 }) },
        ] }
      request = async (action, payload) => {
        assert.equal(action, 'conversation__get')
        assert.equal(payload.mid, 'old-version')
        return { status: 200, data: {
          conversation: { cid: 'cid', agent: { name: 'AI' }, settings: {}, related_workflows: [], related_templates: [] },
          messages: [[assistant('ancestor')], [assistant('old-version'), assistant('new-version')]],
          selected_message_path: ['old-version'], focused_message_mid: 'old-version',
        } }
      }
      assert.equal(await c.fetchConversation('cid', 'old-version'), true)
      assert.equal(c.messagePagination.get(1), 0)
      assert.equal(c.focusedMessageMid.value, 'old-version')
      assert.deepEqual(scrolled, [{ top: 300 }])
    })
    assert.match(focusedHistory, /data-message-mid="old-version"/)
    assert.match(focusedHistory, /message-focused/)
    assert.doesNotMatch(focusedHistory, /data-message-mid="new-version"/)
    const detailComponent = (await server.ssrLoadModule(detail)).default
    const renderer = createRenderer({ createElement: () => ({}), insert() {}, remove() {}, setElementText() {},
      createText: () => ({}), createComment: () => ({}), setText() {}, setComment() {}, parentNode() {}, nextSibling() {}, patchProp() {} })
    const historyRequests = []
    request = (action, payload) => {
      assert.equal(action, 'conversation__get')
      const pending = deferred()
      historyRequests.push({ payload, ...pending })
      return pending.promise
    }
    let mountedDetail
    const mountedApp = renderer.createApp({ setup(props, context) {
      mountedDetail = detailComponent.setup(props, context)
      return () => h('div')
    } })
    mountedApp.use(createPinia())
    mountedApp.provide(ssrContextKey, {})
    mountedApp.use(createI18n({ legacy: false, locale: 'en-US', messages: { 'en-US': locale } }))
    const historyResponse = (cid, mid) => ({ status: 200, data: {
      conversation: { cid, agent: { name: 'AI' }, settings: {}, related_workflows: [], related_templates: [] },
      messages: [[assistant(mid)]], selected_message_path: [mid], focused_message_mid: mid,
    } })
    try {
      mountedApp.mount({})
      const route = globalThis.__chatFailureHarness.route
      route.params.conversationId = 'next-cid'
      route.query.mid = 'next-mid'
      await flush()
      assert.equal(historyRequests.length, 2)
      assert.deepEqual(historyRequests[1].payload, { cid: 'next-cid', mid: 'next-mid' })
      delete route.query.mid
      await flush()
      assert.equal(historyRequests.length, 3)
      assert.deepEqual(historyRequests[2].payload, { cid: 'next-cid' })
      historyRequests[2].resolve(historyResponse('next-cid', 'current'))
      await flush()
      historyRequests[1].resolve(historyResponse('next-cid', 'stale-focus'))
      historyRequests[0].resolve(historyResponse('cid', 'stale-cid'))
      await flush()
      assert.equal(mountedDetail.conversation.value.cid, 'next-cid')
      assert.equal(mountedDetail.messages.value[0][0].mid, 'current')
      assert.equal(mountedDetail.focusedMessageMid.value, '')
      assert.equal(mountedDetail.loading.value, false)
      mountedDetail.messages.value = [[assistant('old-visible'), assistant('new-visible')]]
      mountedDetail.messagePagination.set(0, 1)
      mountedDetail.receiving.value = true
      route.query.mid = 'old-visible'
      await flush()
      assert.equal(historyRequests.length, 3)
      assert.equal(mountedDetail.messagePagination.get(0), 1)
      mountedDetail.receiving.value = false
      await flush()
      assert.equal(historyRequests.length, 4)
      assert.deepEqual(historyRequests[3].payload, { cid: 'next-cid', mid: 'old-visible' })
      historyRequests[3].resolve(historyResponse('next-cid', 'old-visible'))
      await flush()
      assert.equal(mountedDetail.messages.value[0][0].mid, 'old-visible')
      delete route.query.mid
      await flush()
      const lateFork = deferred()
      const count = navigations.length
      request = () => lateFork.promise
      const pendingFork = mountedDetail.forkConversation('old-visible')
      assert.equal(mountedDetail.forking.value, true)
      mountedApp.unmount()
      lateFork.resolve({ status: 200, data: { cid: 'after-unmount' } })
      await pendingFork
      assert.equal(navigations.length, count)
    } finally {
      mountedApp.unmount()
      globalThis.__chatFailureHarness.route.params.conversationId = 'cid'
      globalThis.__chatFailureHarness.route.query = {}
    }
    let retries = 0
    const forkedMessages = []
    const replyProps = { cid: 'cid', mid: 'old-version', authorType: 'A', contentType: 'TXT', status: 'S',
      createTime: 1, content: { text: 'earlier answer' }, metadata: {}, forkable: true, onFork: mid => forkedMessages.push(mid) }
    const replyHtml = await render('/src/components/workspace/chat/ChatMessage.vue', replyProps, async c => { c.forkReply() })
    assert.deepEqual(forkedMessages, ['old-version'])
    assert.match(replyHtml, /aria-label="Fork conversation"/)
    for (const overrides of [{ forkDisabled: true }, { forkLoading: true }, { loading: true },
      { status: 'P' }, { status: 'G' }, { status: 'R' }, { authorType: 'U' }, { forkable: false }]) {
      const html = await render('/src/components/workspace/chat/ChatMessage.vue', { ...replyProps, ...overrides }, async c => { c.forkReply() })
      if (overrides.authorType === 'U' || overrides.forkable === false) assert.doesNotMatch(html, /aria-label="Fork conversation"/)
    }
    assert.deepEqual(forkedMessages, ['old-version'])
    const workflowReply = await render('/src/components/workspace/chat/ChatMessage.vue', {
      ...replyProps, mid: 'workflow-reply', contentType: 'WKF', content: {},
      metadata: { selected_workflow: { title: 'completed workflow', params: {} } },
    }, async c => { c.forkReply() })
    assert.deepEqual(forkedMessages, ['old-version', 'workflow-reply'])
    assert.match(workflowReply, /aria-label="Fork conversation"/)
    const failedProps = { cid: 'cid', mid: 'history', status: 'F', authorType: 'A', contentType: 'WKF', createTime: 1,
      metadata: { selected_workflow: { wid: 'must-not-run' }, error: { message: '<img src=x onerror=alert(1)>' } },
      content: { text: '', reasoning_content: '' }, onRegenerate: () => retries++ }
    const history = await render('/src/components/workspace/chat/ChatMessage.vue', failedProps, async c => { c.regenerate() })
    assert.equal(retries, 1)
    assert.match(history, /&lt;img src=x onerror=alert\(1\)&gt;/)
    assert.equal((history.match(/>Retry<\/button>/g) || []).length, 1)
    assert.doesNotMatch(history, /run-workflow-button|typing-dot|<img/)
    await render('/src/components/workspace/chat/ChatMessage.vue', { ...failedProps, retryDisabled: true }, async c => { c.regenerate() })
    assert.equal(retries, 1)
    await render('/src/components/workspace/chat/ChatMessage.vue', {
      ...failedProps, status:'Z', metadata:{record_id:'saved-stopped',recordStatus:'STOPPED'},
    }, async c => {
      request = async () => ({status:200,data:{rid:'saved-stopped',status:'STOPPED',data:{nodes:[{id:'output'}]}}})
      await c.workflowPanelChange(['history-workflow'])
      assert.equal(c.recordStatus.value,'STOPPED')
      assert.equal(c.workflowData.value.data.nodes[0].id,'output')
      assert.equal(c.failedWorkflow.value,false)
    })
    const previousInterval = globalThis.setInterval
    let poll, appended = 0
    globalThis.setInterval = callback => { poll = callback; return 123 }
    try {
      await render('/src/components/workspace/chat/ChatMessage.vue', {
        ...failedProps, status: 'S', metadata: {selected_workflow:{type:'Workflow',wid:'wf',params:{}}},
        onAppendAnswer: () => appended++,
      }, async c => {
        request = async action => action === 'message__run_workflow' ? {status:200,data:{rid:'cancelled'}}
          : action === 'workflow__check_status' ? {status:200,msg:'STOPPED',data:{data:{nodes:[]}}}
          : {status:200,data:{content:{text:'partial output'}}}
        await c.runWorkflow()
        await poll()
        assert.equal(c.recordStatus.value, 'STOPPED')
        assert.equal(c.runningWorkflow.value, false)
        assert.equal(c.showingRecord.value, true)
        assert.equal(appended, 0)
        assert.equal(c.content.value.text, 'partial output')
      })
      await render('/src/components/workspace/chat/ChatMessage.vue', {
        ...failedProps,status:'S',metadata:{selected_workflow:{type:'Workflow',wid:'wf',params:{}}},onAppendAnswer:() => appended++,
      }, async c => {
        request = async action => action === 'message__run_workflow' ? {status:200,data:{rid:'paused-chat'}}
          : {status:102,msg:'PAUSED',data:{data:{nodes:[],pending_feedback_nodes:['feedback']}}}
        await c.runWorkflow(); await poll()
        assert.equal(c.recordStatus.value,'PAUSED'); assert.equal(c.runningWorkflow.value,false)
        assert.equal(c.showingRecord.value,true); assert.equal(appended,0)
        const before = calls.length; await c.runWorkflow(); assert.equal(calls.length,before)
        request = async action => action === 'workflow__check_status' ? {status:200,data:{data:{nodes:[]}}}
          : {status:200,data:{content:{text:'continued'}}}
        await poll(); assert.equal(c.recordStatus.value,'FINISHED'); assert.equal(appended,1)
      })
    } finally { globalThis.setInterval = previousInterval }
    const legacyFailure = await render('/src/components/workspace/chat/ChatMessage.vue', {
      ...failedProps, contentType: 'TXT', metadata: {}, loading: true,
    }, async () => {})
    assert.match(legacyFailure, /Unable to complete the reply/)
    assert.doesNotMatch(legacyFailure, /typing-dot|run-workflow-button/)
  } finally {
    await server.close()
    globalThis.window = previousWindow
    globalThis.WebSocket = previousSocket
    if (storageDescriptor) Object.defineProperty(globalThis, 'localStorage', storageDescriptor)
    else delete globalThis.localStorage
    if (previousHarness === undefined) delete globalThis.__chatFailureHarness
    else globalThis.__chatFailureHarness = previousHarness
  }
})

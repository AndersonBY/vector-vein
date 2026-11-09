import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick, ref } from 'vue'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createServer } from 'vite'
import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'
import { modelFailureCategory, taskModelFailure, modelHttpStatus } from '../src/utils/taskAgentErrors.js'
async function componentSource(path, id) {
  const filename = fileURLToPath(new URL(path, import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const script = compileScript(descriptor, { id })
  const source = script.content.replace('export default', 'const component =')
  const template = compileTemplate({ source: descriptor.template.content, filename, id,
    compilerOptions: { bindingMetadata: script.bindings } }).code.replace('export function render', 'function render')
  return `${source}\n${template}\ncomponent.render = render; export default component`
}
const renderer = () => createRenderer({
  patchProp: (node, key, _old, value) => { node.props[key] = value },
  insert: (node, parent, anchor) => {
    if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
    node.parent = parent
    const index = anchor ? parent.children.indexOf(anchor) : -1
    if (index < 0) parent.children.push(node)
    else parent.children.splice(index, 0, node)
  },
  remove: node => { if (node?.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1) },
  createElement: type => ({ type, props: {}, children: [], parent: null }),
  createText: text => ({ text }),
  createComment: text => ({ text }),
  setText: (node, text) => { node.text = text },
  setElementText: (node, text) => { node.text = text },
  parentNode: node => node.parent,
  nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
})
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await nextTick() }
const textOf = node => [node?.text || '', ...(node?.children || []).map(textOf)].join(' ')
const findAll = (node, predicate, results = []) => {
  if (predicate(node)) results.push(node)
  for (const child of node.children || []) findAll(child, predicate, results)
  return results
}



test('legacy model failures remain unknown instead of inventing an authentication cause', () => {
  const failure=taskModelFailure({kind:'error',text:'model_outcome_unknown'})
  assert.equal(modelFailureCategory(failure),'unknown')
  assert.equal(modelFailureCategory({category:'<script>'}),'unknown')
  assert.equal(modelHttpStatus({http_status:'401'}),null)
  assert.equal(modelHttpStatus({http_status:401}),401)
  assert.equal(taskModelFailure({kind:'error',text:'workflow_failed'}),null)
})

test('model error component renders actionable reasons, HTTP evidence, settings link and honest legacy fallback', async () => {
  const modules={
    '/model-error-test.js':await componentSource('../src/views/Workspace/TaskAgent/TaskAgentModelError.vue','model-error'),
    '@/utils/taskAgentErrors':await readFile(new URL('../src/utils/taskAgentErrors.js',import.meta.url),'utf8'),
  }
  const server=await createServer({configFile:false,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{name:'model-error-test',resolveId:id=>Object.hasOwn(modules,id)?id:undefined,load:id=>modules[id]}],server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true},appType:'custom'})
  let app
  try {
    const component=(await server.ssrLoadModule('/model-error-test.js')).default
    const failure=ref({category:'authentication',http_status:401,response_rejected:true})
    const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>null}},{path:'/settings',name:'settings',component:{render:()=>null}}]})
    await router.push('/');await router.isReady()
    app=renderer().createApp({render:()=>h(component,{failure:failure.value,modelConfig:{selected_model:'deepseek-v4.1-flash',model_id:'deepseek-flash'}})})
    app.component('AAlert',{inheritAttrs:false,setup:(_,{attrs,slots})=>()=>h('Alert',attrs,[attrs.message,...(slots.description?.()||[])])})
    const messages=JSON.parse(await readFile(new URL('../src/locales/zh-CN.json',import.meta.url),'utf8'))
    app.use(router);app.use(createI18n({legacy:false,locale:'zh-CN',messages:{'zh-CN':messages}}))
    const root={children:[]};app.mount(root);await flush()
    assert.match(textOf(root),/模型接口认证失败.*401/)
    assert.match(textOf(root),/API KEY/)
    assert.match(textOf(root),/deepseek-v4.1-flash/)
    assert.match(textOf(root),/deepseek-flash/)
    assert.equal(findAll(root,node=>node.type==='a')[0].props.href,'/settings')
    failure.value={category:'unknown'};await nextTick()
    assert.match(textOf(root),/没有保留更具体的原因/)
    assert.doesNotMatch(textOf(root),/认证失败|model_outcome_unknown/)
    assert.match(textOf(root),/无法据此确认服务端是否已经处理或计费/)
    failure.value={category:'parameter',http_status:422,parameter:'reasoning_effort',response_rejected:true};await nextTick()
    assert.match(textOf(root),/模型不接受当前请求参数.*422/)
    assert.match(textOf(root),/reasoning_effort/)
    app.unmount();app=null
  } finally {app?.unmount();await server.close()}
})

test('application router exposes Skills and MCP management routes', async () => {
  const { taskAgentSpaceRoute } = await import('../src/router/modules/taskAgent.js')
  const names = taskAgentSpaceRoute.children.map(route => route.name)
  for (const name of ['taskAgentSkills', 'taskAgentSkillCreate', 'taskAgentSkillDetail', 'taskAgentMCP']) {
    assert.ok(names.includes(name), name)
  }
})

test('integration error helper maps skills and mcp codes to localized messages without leaking raw messages', async () => {
  const { formatIntegrationError, extractSkillDiagnostics } = await import('../src/utils/taskAgentErrors.js')
  const zh = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
  const en = JSON.parse(await readFile(new URL('../src/locales/en-US.json', import.meta.url), 'utf8'))
  const lookup = (dict, key) => key.split('.').reduce((acc, part) => acc?.[part], dict) || key
  const tZh = key => lookup(zh, key)
  const tEn = key => lookup(en, key)

  const conflictMsg = formatIntegrationError({ status: 409, msg: 'Raw conflict' }, tZh)
  assert.match(conflictMsg, /已被其他操作更新/)
  assert.doesNotMatch(conflictMsg, /Raw conflict/)

  const authMsg = formatIntegrationError({
    status: 400,
    msg: 'Bearer SUPER_SECRET_TOKEN_999',
    data: { integration_error: { kind: 'mcp', code: 'authentication_failed', message: 'Bearer SUPER_SECRET_TOKEN_999' } },
  }, tEn)
  assert.match(authMsg, /authentication failed/i)
  assert.doesNotMatch(authMsg, /SUPER_SECRET_TOKEN_999/)

  const skillResp = {
    status: 400,
    data: {
      integration_error: {
        kind: 'skills',
        code: 'invalid_frontmatter',
        diagnostics: ['Missing description field in YAML frontmatter'],
      },
    },
  }
  assert.match(formatIntegrationError(skillResp, tZh), /YAML frontmatter/)
  assert.deepEqual(extractSkillDiagnostics(skillResp), ['Missing description field in YAML frontmatter'])
})

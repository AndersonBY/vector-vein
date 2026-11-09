import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick, ref } from 'vue'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createServer } from 'vite'
import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'
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



test('workflow feedback keeps drafts across polling, sends exact checkpoint identity, and clears a later checkpoint', async () => {
  const source=await componentSource('../src/views/Workspace/TaskAgent/TaskAgentWorkflowRuns.vue','workflow-runs')
  const server=await createServer({configFile:false,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{name:'workflow-feedback-test',resolveId:id=>id==='/workflow-runs-test.js'?id:undefined,load:id=>id==='/workflow-runs-test.js'?source:undefined}],server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true},appType:'custom'})
  let app
  try {
    const component=(await server.ssrLoadModule('/workflow-runs-test.js')).default
    const snapshot=generation=>[{job_id:'job',run_id:'run',workflow_id:'workflow',title:'Report workflow',status:'PAUSED',feedback:[{run_id:'run',generation,questions:[{node_id:'review',prompt:'Review report'}],resume_ready:false}]}]
    const runs=ref(snapshot(0))
    const calls=[]
    const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>null}},{path:'/workflow/:workflowId',name:'WorkflowUse',component:{render:()=>null}}]})
    await router.push('/');await router.isReady()
    app=renderer().createApp({render:()=>h(component,{runs:runs.value,onFeedback:value=>calls.push(value)})})
    const messages=JSON.parse(await readFile(new URL('../src/locales/zh-CN.json',import.meta.url),'utf8'))
    app.use(router);app.use(createI18n({legacy:false,locale:'zh-CN',messages:{'zh-CN':messages}}))
    app.component('ATextarea',{props:['value'],emits:['update:value'],setup:(props,{emit,attrs})=>()=>h('ATextarea',{...attrs,value:props.value,'onUpdate:value':value=>emit('update:value',value)})})
    app.component('AButton',{setup:(_,{attrs,slots})=>()=>h('AButton',attrs,slots.default?.())})
    const root={children:[]};app.mount(root);await flush()
    assert.equal(findAll(root,n=>n.type==='AButton')[0].props.disabled,true)
    findAll(root,n=>n.type==='ATextarea')[0].props['onUpdate:value']('Reviewed')
    await nextTick();runs.value=snapshot(0);await flush()
    assert.equal(findAll(root,n=>n.type==='ATextarea')[0].props.value,'Reviewed')
    findAll(root,n=>n.type==='AButton')[0].props.onClick()
    assert.deepEqual(calls,[{run_id:'run',generation:0,answers:[{node_id:'review',content:'Reviewed'}]}])
    runs.value=snapshot(1);await flush()
    assert.equal(findAll(root,n=>n.type==='ATextarea')[0].props.value,undefined)
    assert.equal(findAll(root,n=>n.type==='AButton')[0].props.disabled,true)
    assert.match(textOf(root),/Report workflow/)
    app.unmount();app=null
  } finally {app?.unmount();await server.close()}
})

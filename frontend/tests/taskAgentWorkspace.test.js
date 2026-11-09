import { iconButtonFixture } from './taskAgentButtonFixture.js'
import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick, ref } from 'vue'
import { createI18n } from 'vue-i18n'
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
  createElement: type => ({ type, props: {}, style: {}, children: [], parent: null }),
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




test('workspace tabs preserve independent previews, reject stale task responses and assemble UTF-8 tool pages', async () => {
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    '/workspace-test.js': (await componentSource('../src/views/Workspace/TaskAgent/TaskAgentWorkspace.vue', 'workspace-tabs')).replace("'ant-design-vue'", "'/workspace-message.js'").replace("'vue-markdown-render'", "'/workspace-markdown.js'"),
    '@/api/taskAgent': 'export const taskAgentAPI=(action,payload)=>globalThis.__workspaceAPI(action,payload)',
    '@/utils/taskAgentTimeline': await readFile(new URL('../src/utils/taskAgentTimeline.js', import.meta.url), 'utf8'),
    '@/components/TextOutput.vue': 'import {h} from "vue";export default{props:["text"],setup:props=>()=>h("RenderedText",{},props.text)}',
    '/workspace-markdown.js': 'import {h} from "vue";export default{props:["source","options"],setup:props=>()=>h("SafeMarkdown",{options:props.options},props.source)}',
    '@/icons': 'export const DocDetail={render:()=>null},FolderOpen=DocDetail,Refresh=DocDetail,CheckOne=DocDetail,CircleFourLine=DocDetail,LoadingFour=DocDetail,Plus=DocDetail,Close=DocDetail,OffScreenOne=DocDetail,FullScreenOne=DocDetail,Tool=DocDetail,Robot=DocDetail,ListOne=DocDetail; export const Delete=DocDetail,Undo=DocDetail,Star=DocDetail,Down=DocDetail,OpenExternal=DocDetail;',
    '/workspace-message.js': 'export const message={error:()=>{}}',
  }
  const server=await createServer({configFile:false,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{name:'workspace-tabs-test',resolveId:id=> Object.hasOwn(modules,id)?id:undefined,load:id=>modules[id]}],server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true},appType:'custom'})
  let app
  try {
    const taskId=ref('one'), vm=ref(null), calls=[], delayed=[], knowledgeDelayed=[]
    const tool={id:'tool-one',kind:'tool',tool_name:'bash',status:'success',arguments:{command:'test'},result_event_id:'receipt',result:{preview:'Preview'}}
    const entries=ref([tool])
    globalThis.__workspaceAPI=async(action,payload)=>{
      calls.push({action,payload})
      if(action==='files')return{status:200,data:{files:[{path:'outputs/slow.md',name:'slow.md',size:10},{path:'outputs/other.md',name:'other.md',size:20}],limited:false}}
      if(action==='preview_file'&&payload.path==='outputs/slow.md')return new Promise(resolve=>delayed.push(resolve))
      if(action==='preview_file'&&payload.path.startsWith('.knowledge/'))return new Promise(resolve=>knowledgeDelayed.push(resolve))
      if(action==='preview_file'&&payload.path.endsWith('.html'))return{status:200,data:{kind:'text',markdown:false,text:'<h1>Local HTML</h1><script>parent.document.title="NO"</script>'}}
      if(action==='preview_file')return{status:200,data:{kind:'text',markdown:true,text:'Other file'}}
      if(action==='tool_result'){
        const bytes=Buffer.from('中文输出 176','utf8')
        return{status:200,data:{data:(payload.offset?bytes.subarray(2):bytes.subarray(0,2)).toString('base64'),nextOffset:payload.offset?bytes.length:2,eof:Boolean(payload.offset)}}
      }
    }
    const component=(await server.ssrLoadModule('/workspace-test.js')).default
    app=renderer().createApp({render:()=>h(component,{ref:vm,taskId:taskId.value,entries:entries.value})})
    const messages=JSON.parse(await readFile(new URL('../src/locales/zh-CN.json',import.meta.url),'utf8'))
    app.use(createI18n({legacy:false,locale:'zh-CN',messages:{'zh-CN':messages}}))
    for(const name of ['AButton','AInput','AAlert','AEmpty','ASpin','ASelect','ARadioGroup','ARadioButton'])app.component(name,{inheritAttrs:false,setup:(_,{attrs,slots})=>()=>h(name,attrs,slots.default?.())})
    const root={children:[]};app.mount(root);await flush()
    vm.value.showPreview('outputs/slow.md');await flush()
    vm.value.showPreview('outputs/other.md');await flush()
    delayed.shift()({status:200,data:{kind:'text',markdown:true,text:'Slow file'}});await flush()
    assert.match(textOf(root),/Other file/)
    assert.doesNotMatch(textOf(root),/Slow file/)
    const slowTab=findAll(root,node=>node.props?.role==='tab'&&textOf(node).includes('slow.md'))[0]
    slowTab.props.onClick();await flush();assert.match(textOf(root),/Slow file/)
    const view = findAll(root,node=>node.type==='ARadioGroup')[0]
    view.props['onUpdate:value']('source');await flush()
    assert.equal(findAll(root,node=>node.type==='RenderedText').length,0)
    assert.match(textOf(root),/Slow file/)
    vm.value.showPreview('outputs/preview.html');await flush()
    const frame = findAll(root,node=>node.type==='iframe')[0]
    assert.equal(frame.props.sandbox,'')
    assert.equal(frame.props.referrerpolicy,'no-referrer')
    assert.match(frame.props.srcdoc,/Content-Security-Policy/)
    assert.match(frame.props.srcdoc,/default-src 'none'/)
    assert.match(frame.props.srcdoc,/Local HTML/)
    const workspace = findAll(root,node=>node.type==='aside')[0]
    let prevented = false
    workspace.props.onClickCapture({
      target:{closest:()=>({getAttribute:()=> './.knowledge/Notes/report.pdf'})},
      preventDefault:()=>{prevented=true},stopPropagation:()=>{},
    });await flush()
    assert.equal(prevented,true)
    assert.equal(calls.at(-1).action,'preview_file')
    assert.equal(calls.at(-1).payload.path,'.knowledge/Notes/report.pdf')
    const nativeLabels = ['reveal_file','open_file'].map(key=>messages.workspace.taskAgentSpace[key])
    assert.equal(findAll(root,node=>nativeLabels.includes(node.props?.['aria-label'])).length,0)
    knowledgeDelayed.shift()({status:200,data:{kind:'text',markdown:false,text:'Extracted PDF body <script>untrusted()</script>',read_only:true}})
    await flush()
    assert.match(textOf(root),/Extracted PDF body/)
    assert.equal(findAll(root,node=>node.type==='iframe').length,0)
    assert.equal(findAll(root,node=>node.type==='pre').length,1)
    assert.equal(findAll(root,node=>/reveal_file|open_file|在文件夹中|打开文件/.test(node.props?.['aria-label'] || '')).length,0)
    assert.equal(findAll(root,node=>nativeLabels.includes(node.props?.['aria-label'])).length,0)
    vm.value.showPreview('.knowledge/Notes/untrusted.md');await flush()
    knowledgeDelayed.shift()({status:200,data:{kind:'text',markdown:true,text:'<img src=x onerror="untrusted()">',read_only:true}})
    await flush()
    assert.equal(findAll(root,node=>node.type==='SafeMarkdown')[0].props.options.html,false)
    assert.equal(findAll(root,node=>node.type==='RenderedText').length,0)
    slowTab.props.onClick();await flush()
    assert.equal(findAll(root,node=>node.type==='ARadioGroup')[0].props.value,'source')
    vm.value.openTool(tool);await flush();await flush()
    const more=findAll(root,node=>node.type==='AButton'&&String(node.props?.['aria-label'] || '').includes('继续读取'))[0]
    await more.props.onClick();await flush()
    assert.match(textOf(root),/中文输出 176/)
    assert.equal(findAll(root,node=>node.type==='AButton'&&String(node.props?.['aria-label'] || '').includes('继续读取')).length,0)
    assert.deepEqual(calls.filter(call=>call.action==='tool_result').map(call=>call.payload.offset),[0,2])
    entries.value=[{...tool,command_status:'unknown',command_status_reason:'turn_ended_without_terminal_observation'}];await flush()
    assert.match(findAll(root,node=>node.type==='AAlert')[0].props.message,/本轮对话已结束.*不代表命令现在仍在运行/)
    const badQuery={id:'bad-query',kind:'tool',tool_name:'check_background_command',status:'error',error_code:'background_session_missing',arguments:{session_id:'wrong-handle'},result:{preview:'Command handle unavailable'}}
    entries.value.push(badQuery);vm.value.openTool(badQuery);await flush()
    assert.match(textOf(root),/查询失败/)
    assert.match(findAll(root,node=>node.type==='AAlert')[0].props.message,/查询失败不代表原命令执行失败/)
    assert.equal(calls.filter(call=>call.action==='tool_result').length,2)
    findAll(root,node=>node.props?.['aria-label']==='关闭 slow.md')[0].props.onClick();await flush()
    vm.value.showPreview('outputs/slow.md');await flush()
    taskId.value='two';await flush()
    delayed.shift()({status:200,data:{kind:'text',markdown:true,text:'OLD TASK DATA'}});await flush()
    assert.doesNotMatch(textOf(root),/OLD TASK DATA/)
    assert.equal(findAll(root,node=>node.props?.role==='tab').length,1)
    assert.equal(calls.at(-1).payload.task_id,'two')
  } finally { app?.unmount();await server.close();delete globalThis.__workspaceAPI }
})

test('Project workspace browses without a task and isolates same-named files and late previews', async () => {
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    '/project-workspace-test.js': (await componentSource('../src/views/Workspace/TaskAgent/TaskAgentWorkspace.vue', 'project-workspace')).replace("'ant-design-vue'", "'/workspace-message.js'"),
    '@/api/taskAgent': 'export const taskAgentAPI=(action,payload)=>globalThis.__projectWorkspaceAPI(action,payload)',
    '@/utils/taskAgentTimeline': await readFile(new URL('../src/utils/taskAgentTimeline.js', import.meta.url), 'utf8'),
    '@/components/TextOutput.vue': 'import {h} from "vue";export default{props:["text"],setup:props=>()=>h("RenderedText",{},props.text)}',
    '@/icons': 'export const DocDetail={render:()=>null},FolderOpen=DocDetail,Refresh=DocDetail,CheckOne=DocDetail,CircleFourLine=DocDetail,LoadingFour=DocDetail,Plus=DocDetail,Close=DocDetail,OffScreenOne=DocDetail,FullScreenOne=DocDetail,Tool=DocDetail,Robot=DocDetail,ListOne=DocDetail; export const Delete=DocDetail,Undo=DocDetail,Star=DocDetail,Down=DocDetail,OpenExternal=DocDetail;',
    '/workspace-message.js': 'export const message={error:()=>{}}',
  }
  const server=await createServer({configFile:false,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{name:'project-workspace-test',resolveId:id=> Object.hasOwn(modules,id)?id:undefined,load:id=>modules[id]}],server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true},appType:'custom'})
  let app
  try {
    const projectId=ref('one'), project=ref({roots:['E:/one','E:/shared']}), vm=ref(null), calls=[]
    let resolveOld
    globalThis.__projectWorkspaceAPI=async(action,payload)=>{
      calls.push({action,payload})
      assert.equal(Object.hasOwn(payload,'task_id'),false)
      if(action==='project_files')return{status:200,data:{files:[{path:`project-files/${payload.root_id}/same.md`,name:'same.md',size:20}],limited:false}}
      assert.equal(action,'project_preview_file')
      if(payload.project_id==='one')return new Promise(resolve=>{resolveOld=resolve})
      return{status:200,data:{kind:'text',markdown:true,text:payload.path.includes('/1/')?'Secondary root':'Current project'}}
    }
    const component=(await server.ssrLoadModule('/project-workspace-test.js')).default
    app=renderer().createApp({render:()=>h(component,{ref:vm,projectId:projectId.value,project:project.value})})
    const messages=JSON.parse(await readFile(new URL('../src/locales/zh-CN.json',import.meta.url),'utf8'))
    app.use(createI18n({legacy:false,locale:'zh-CN',messages:{'zh-CN':messages}}))
    for(const name of ['AButton','AInput','AAlert','AEmpty','ASpin','ASelect','ARadioGroup','ARadioButton'])app.component(name,{inheritAttrs:false,setup:(_,{attrs,slots})=>()=>h(name,attrs,slots.default?.())})
    const root={children:[]};app.mount(root);await flush()
    vm.value.showPreview('project-files/0/same.md');await flush()
    projectId.value='two';project.value={roots:['E:/two','E:/shared']};await flush()
    vm.value.showPreview('project-files/0/same.md');await flush()
    resolveOld({status:200,data:{kind:'text',markdown:true,text:'OLD PROJECT DATA'}});await flush()
    assert.match(textOf(root),/Current project/)
    assert.doesNotMatch(textOf(root),/OLD PROJECT DATA/)
    findAll(root,node=>node.props?.['aria-label']==='选择 Project 文件')[0].props.onClick();await flush()
    findAll(root,node=>node.type==='ASelect')[0].props['onUpdate:value']('1');await flush()
    vm.value.showPreview('project-files/1/same.md');await flush()
    assert.match(textOf(root),/Secondary root/)
    const tabs=findAll(root,node=>node.props?.role==='tab')
    assert.equal(tabs.length,3)
    assert(tabs.some(tab=>tab.props.title==='E:/two/same.md'))
    assert(tabs.some(tab=>tab.props.title==='E:/shared/same.md'))
    project.value={roots:['E:/replacement']};await flush()
    assert.equal(findAll(root,node=>node.props?.role==='tab').length,1)
    assert.equal(calls.at(-1).payload.root_id,'0')
    assert.equal(calls.at(-1).payload.project_id,'two')
    assert(calls.every(call=>call.action.startsWith('project_')))
  } finally {app?.unmount();await server.close();delete globalThis.__projectWorkspaceAPI}
})

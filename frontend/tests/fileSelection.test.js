import assert from 'node:assert/strict'
import test from 'node:test'
import {fileURLToPath} from 'node:url'
import {readFile} from 'node:fs/promises'
import {createSSRApp} from 'vue'
import {renderToString} from 'vue/server-renderer'
import {createI18n} from 'vue-i18n'
import {createServer} from 'vite'
import vue from '@vitejs/plugin-vue'

test('native file selection reports file names, preserves canceled selections and uses a complete error message', async()=>{
  const previousWindow=globalThis.window,previousMessages=globalThis.__fileSelectionMessages
  const successes=[],errors=[]
  globalThis.__fileSelectionMessages={successes,errors}
  let choose=async()=>['C:\\资料\\报告.pdf','/tmp/图像.png']
  globalThis.window={pywebview:{api:{open_file_dialog:(...args)=>choose(...args)}}}
  const server=await createServer({configFile:false,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[vue(),{
    name:'file-selection-fixture',enforce:'pre',
    transform(source,id){if(id.endsWith('/UploaderFieldUse.vue'))return source.replace("from 'ant-design-vue'","from 'virtual:selection-ant'")},
    resolveId(id){if(id==='virtual:selection-ant')return '\0selection-ant'},
    load(id){if(id==='\0selection-ant')return 'export const message={success:x=>globalThis.__fileSelectionMessages.successes.push(x),error:x=>globalThis.__fileSelectionMessages.errors.push(x)}'},
  }],resolve:{alias:{'@':fileURLToPath(new URL('../src',import.meta.url))}},server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true},appType:'custom'})
  try{
    const component=(await server.ssrLoadModule('/src/components/workspace/UploaderFieldUse.vue')).default
    for(const locale of ['zh-CN','en-US']){
      const selected=[]
      const app=createSSRApp({...component,ssrRender:undefined,render:()=>null,async setup(props,ctx){
        const c=component.setup(props,ctx)
        await c.selectFile({})
        assert.deepEqual([...selected],['C:\\资料\\报告.pdf','/tmp/图像.png'])
        assert.match(successes.at(-1),/报告\.pdf、图像\.png/)
        assert.doesNotMatch(successes.at(-1),/\{file\}|C:\\/)
        const count=successes.length
        choose=async()=>[]
        await c.selectFile({})
        assert.equal(successes.length,count)
        assert.equal(selected.length,2)
        choose=async()=>null
        await c.selectFile({})
        assert.equal(selected.length,2)
        choose=async()=>{throw new Error('fixture selection failure')}
        await c.selectFile({})
        assert.equal(selected.length,2)
        assert.equal(c.uploading.value,false)
        assert.equal(errors.at(-1),locale==='zh-CN'?'无法选择文件，请重试。':'Could not select files. Please try again.')
        choose=async()=>['C:\\资料\\报告.pdf','/tmp/图像.png']
        return ()=>null
      }},{modelValue:selected,multiple:true,singleButton:true})
      app.use(createI18n({legacy:false,locale,messages:{[locale]:JSON.parse(await readFile(new URL('../src/locales/'+locale+'.json',import.meta.url),'utf8'))}}))
      await renderToString(app)
    }
  }finally{await server.close();globalThis.window=previousWindow;globalThis.__fileSelectionMessages=previousMessages}
})

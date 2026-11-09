import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

const files = [
  'views/Workspace/Database/KnowledgeBaseDetail.vue',
  'components/workspace/database/KnowledgeBaseCatalog.vue',
  'components/workspace/database/RelationalDatabaseTable.vue',
  'views/Workspace/Database/RelationalDatabaseDetail.vue',
  'views/Workspace/Database/RelationalDatabaseTableDetail.vue',
  'views/Workspace/Database/RelationalDatabaseTableCreate.vue',
  'views/Workspace/WorkflowSpace.vue',
  'views/Workspace/WorkflowScheduleManager.vue',
  'views/Workspace/WorkflowEditor.vue',
  'components/workspace/WorkflowUse.vue',
]
const source = file => readFile(new URL(`../src/${file}`, import.meta.url), 'utf8')
const translations = await Promise.all(['en-US', 'zh-CN'].map(async locale => JSON.parse(await source(`locales/${locale}.json`))))
const walk = (node, visit, ancestors = []) => {
  visit(node, ancestors)
  for (const child of node.children || []) walk(child, visit, [...ancestors, node])
}

for (const file of files) test(`${file}: compact actions have localized labels, icon slots and no swallowed dialogs`, async () => {
  const text = await source(file)
  const { descriptor, errors } = parse(text, { filename: file })
  assert.deepEqual(errors, [])
  const compiled = compileScript(descriptor, { id: file })
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: file, id: file,
    compilerOptions: { bindingMetadata: compiled.bindings } }).errors, [])
  let count = 0
  walk(descriptor.template.ast, (node, ancestors) => {
    if (node.tag !== 'IconButton') return
    count++
    assert.ok(!node.props.some(prop => prop.type === 7 && prop.name === 'show'),
      'Tooltip roots cannot receive v-show; put visibility on a native wrapper')
    const label = node.props.find(prop => prop.type === 7 && prop.name === 'bind' && prop.arg?.content === 'text')
    assert.ok(label?.exp?.content.includes('t('), 'Every icon action needs localized tooltip/accessible text')
    for (const [, key] of label.exp.content.matchAll(/'([^']+)'/g)) {
      for (const locale of translations) assert.ok(key.split('.').reduce((value, part) => value?.[part], locale), key)
    }
    assert.ok(node.children.some(child => child.tag === 'template' && child.props.some(prop => prop.name === 'slot' && prop.arg?.content === 'icon')))
    assert.ok(node.children.every(child => child.type === 3 || child.type === 2 && !child.content.trim() ||
      child.tag === 'template' && child.props.some(prop => prop.name === 'slot' && prop.arg?.content === 'icon')),
    'IconButton has no default slot: dialogs must remain outside it')
    assert.ok(!ancestors.some(parent => parent.tag === 'a-tooltip'), 'Shared IconButton already supplies its tooltip')
  })
  assert.ok(count > 0)
})

test('primary workflow choices, exit confirmations and wizard navigation retain wording', async () => {
  const use = await source('components/workspace/WorkflowUse.vue')
  for (const click of ['resumeWorkflow', 'stopWorkflow', "runWorkflow('record')", "runWorkflow('latest')"]) {
    assert.ok(use.includes(`@click="${click}"`))
    assert.ok(new RegExp(`<a-button[^>]*@click="${click.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"[^>]*>[\\s\\S]*?{{`).test(use), click)
  }
  const editor = await source('views/Workspace/WorkflowEditor.vue')
  assert.match(editor, /<a-button[^>]*@click="exitNoSave"[^>]*>\s*{{ t\('workspace.workflowEditor.exit_without_save'\) }}/)
  assert.match(editor, /<a-button[^>]*@click="saveAndExit"[^>]*>\s*{{ t\('workspace.workflowEditor.save_and_exit'\) }}/)
  const create = await source('views/Workspace/Database/RelationalDatabaseTableCreate.vue')
  for (const key of ['previous_step', 'next_step', 'finish']) assert.ok(create.includes(`{{ t('common.${key}') }}`))
})

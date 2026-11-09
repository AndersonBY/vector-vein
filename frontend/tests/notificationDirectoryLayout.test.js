import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

const find = (node, predicate) => [...(predicate(node) ? [node] : []), ...(node.children || []).flatMap(child => find(child, predicate))]
const attr = (node, name) => node.props?.find(prop => prop.type === 6 && prop.name === name)?.value?.content
const directive = (node, name, arg) => node.props?.find(prop => prop.type === 7 && prop.name === name && prop.arg?.content === arg)
async function template(file) {
  const { descriptor, errors } = parse(await readFile(new URL(`../src/${file}`, import.meta.url), 'utf8'), { filename: file })
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: file })
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: file, id: file,
    compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
  return descriptor.template.ast
}

test('notification switch and labeled test action share a wrapping operation area beside the description', async () => {
  const ast = await template('components/settings/NotificationSettings.vue')
  const row = find(ast, node => attr(node, 'class') === 'notification-row')[0]
  assert.equal(attr(row, 'wrap'), 'wrap')
  const copy = find(row, node => attr(node, 'class') === 'notification-copy')[0]
  assert.match(copy.loc.source, /notifications_enable/)
  assert.match(copy.loc.source, /notifications_description/)
  const actions = find(row, node => attr(node, 'class') === 'notification-actions')[0]
  assert.equal(attr(actions, 'wrap'), 'wrap')
  assert.equal(find(actions, node => node.tag === 'a-switch').length, 1)
  const buttons = find(actions, node => node.tag === 'a-button')
  assert.equal(buttons.length, 1)
  assert.notEqual(attr(buttons[0], 'type'), 'primary')
  assert.equal(directive(buttons[0], 'on', 'click').exp.content, 'testNotification')
  assert.equal(directive(buttons[0], 'bind', 'loading').exp.content, 'testing')
  assert.match(buttons[0].loc.source, /{{ t\('settings.notifications_test'\) }}/)
  assert.equal(find(buttons[0], node => node.tag === 'Remind').length, 1)
  assert.equal(find(ast, node => node.tag === 'IconButton').length, 0)
})

test('all three directory fields keep a full-path title and their picker in the same row', async () => {
  const ast = await template('views/Settings.vue')
  const rows = find(ast, node => attr(node, 'class') === 'directory-picker')
  assert.equal(rows.length, 3)
  for (const key of ['output_folder', 'log_path', 'data_path']) {
    const row = rows.find(node => node.loc.source.includes(`selectFolder('${key}')`))
    assert.ok(row, key)
    const path = find(row, node => attr(node, 'class') === 'directory-path')[0]
    assert.equal(directive(path, 'bind', 'title').exp.content, `settingForm.data.${key}`)
    assert.ok(path.loc.source.includes(`{{ settingForm.data.${key} }}`))
    const button = find(row, node => node.tag === 'IconButton')[0]
    assert.equal(directive(button, 'bind', 'text').exp.content, "t('settings.select_folder')")
    assert.equal(directive(button, 'on', 'click').exp.content, `selectFolder('${key}')`)
  }
})

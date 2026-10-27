import assert from 'node:assert/strict'
import test from 'node:test'
import { readdir, readFile } from 'node:fs/promises'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { PhPlus, PhStar } from '@phosphor-icons/vue'
import * as icons from '../src/icons/index.js'

const render = (Icon, props = {}) => renderToString(createSSRApp({ render: () => h(Icon, props) }))

test('every desktop icon import resolves and renders a real SVG', async () => {
  const files = await readdir(new URL('../src/', import.meta.url), { recursive: true })
  const consumed = new Set()
  for (const file of files.filter(file => /\.(js|vue)$/.test(file))) {
    const source = await readFile(new URL(`../src/${file.replaceAll('\\', '/')}`, import.meta.url), 'utf8')
    assert.ok(!source.includes('@icon-park'), file)
    for (const match of source.matchAll(/import\s*\{([^}]+)\}\s*from\s*['"]@\/icons['"]/g)) {
      for (const name of match[1].split(',').map(name => name.trim()).filter(Boolean)) consumed.add(name)
    }
  }
  for (const name of consumed) {
    assert.ok(icons[name], name)
    const svg = await render(icons[name])
    assert.match(svg, /<svg[^>]+width="1em"/, name)
    assert.match(svg, /<path/, name)
  }
})

test('adapter preserves size, first fill color, theme, attributes and loading animation', async () => {
  const adapted = await render(icons.Add, { size: 32, fill: ['#123456', '#ffffff'], theme: 'outline', spin: true, class: 'consumer', 'aria-label': 'Add' })
  const actual = await render(PhPlus, { size: 32, color: '#123456', weight: 'regular', class: ['vv-icon', 'consumer', 'vv-icon-spin'], 'aria-label': 'Add' })
  assert.equal(adapted, actual)
  for (const [theme, weight] of [['filled', 'fill'], ['two-tone', 'duotone'], ['outline', 'regular']]) {
    assert.equal(await render(icons.Star, { theme }), await render(PhStar, { size: '1em', color: 'currentColor', weight, class: ['vv-icon'] }))
  }
  assert.doesNotMatch(await render(icons.LoadingFour), /vv-icon-spin/)
  const css = await readFile(new URL('../src/icons/icons.css', import.meta.url), 'utf8')
  assert.match(css, /\.vv-icon-spin\s*\{\s*animation: vv-icon-spin 1s linear infinite/)
  assert.match(css, /rotate\(360deg\)/)
})

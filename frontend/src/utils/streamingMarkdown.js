export function streamingMarkdownPlugin(md, { copyLabel = 'Copy' } = {}) {
  // Inline rules run after code spans have already claimed their contents.
  md.inline.ruler.before('escape', 'bracket_math', (state, silent) => {
    const open = state.src.slice(state.pos, state.pos + 2)
    if (open !== '\\(' && open !== '\\[') return false
    const end = state.src.indexOf(open === '\\(' ? '\\)' : '\\]', state.pos + 2)
    if (end < 0) return false
    if (!silent) {
      const token = state.push(open === '\\(' ? 'math_inline' : 'math_block', 'math', 0)
      token.content = state.src.slice(state.pos + 2, end)
    }
    state.pos = end + 2
    return true
  })
  md.inline.ruler.before('math_inline', 'currency', (state, silent) => {
    if (state.src[state.pos] !== '$' || state.src[state.pos + 1] === '$') return false
    const rest = state.src.slice(state.pos + 1)
    const end = rest.indexOf('$')
    const body = end < 0 ? rest : rest.slice(0, end)
    if (end >= 0 && /^\d[\d.,]*$/.test(body)) return false
    if (!/^\d/.test(body) || /[+*=^_{}\\]/.test(body) || /^\d[\d.,]*\s*[-/]\s*\d/.test(body)) return false
    if (!silent) state.pending += '$'
    state.pos++
    return true
  })
  const fenceRule = md.block.ruler.__rules__.find(rule => rule.name === 'fence')
  const parseFence = fenceRule.fn
  md.block.ruler.at('fence', (state, start, end, silent) => {
    const result = parseFence(state, start, end, silent)
    if (result && !silent) {
      const token = state.tokens.at(-1)
      const last = token.map[1] - 1
      // Read while the parser still has the current list/blockquote line offsets.
      const closing = state.src.slice(state.bMarks[last] + state.tShift[last], state.eMarks[last]).match(/^(`+|~+)\s*$/)?.[1]
      token.meta = { closed: last > start && closing?.[0] === token.markup[0] && closing.length >= token.markup.length }
    }
    return result
  }, { alt: fenceRule.alt })
  const fence = md.renderer.rules.fence
  md.renderer.rules.fence = (tokens, index, ...args) => {
    const token = tokens[index]
    const language = token.info.trim().split(/\s+/)[0]
    const code = encodeURIComponent(token.content)
    return `<div class="code-block" data-code="${md.utils.escapeHtml(code)}" data-mermaid="${language === 'mermaid' && token.meta.closed}"><div class="header"><span class="language">${md.utils.escapeHtml(language)}</span><button type="button" class="copy-container" aria-label="${md.utils.escapeHtml(copyLabel)}" title="${md.utils.escapeHtml(copyLabel)}"></button></div>${fence(tokens, index, ...args)}</div>`
  }
}

const scalar = value => value === null || ['string', 'boolean'].includes(typeof value)
  || typeof value === 'number' && Number.isFinite(value)

// Inspect keys before JSON.parse can collapse duplicates in a literal draft.
function duplicateKey(source, insensitive = false) {
  const tokens = source.match(/"(?:[^"\\]|\\.)*"|[{}[\]:,]/g) || []
  const keys = new Set()
  let depth = 0
  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i]
    if (token === '{' || token === '[') depth++
    else if (token === '}' || token === ']') depth--
    else if (depth === 1 && token.startsWith('"') && tokens[i + 1] === ':') {
      const key = JSON.parse(token)
      const comparable = insensitive ? key.toLowerCase() : key
      if (keys.has(comparable)) return true
      keys.add(comparable)
    }
  }
  return false
}

export function parseHttpValue(source, kind) {
  let value = source
  if (typeof source === 'string') {
    try { value = JSON.parse(source) } catch { return { error: 'invalid_json' } }
    if (kind !== 'json' && duplicateKey(source, kind === 'headers')) return { error: 'duplicate_key' }
  }
  if (kind === 'json') {
    const finite = value => scalar(value) || value && typeof value === 'object' && Object.values(value).every(finite)
    return finite(value) ? { value } : { error: 'invalid_json' }
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return { error: 'object_required' }
  const keys = new Set()
  for (const [key, item] of Object.entries(value)) {
    if (!key.trim()) return { error: 'empty_key' }
    const comparable = kind === 'headers' ? key.toLowerCase() : key
    if (keys.has(comparable)) return { error: 'duplicate_key' }
    keys.add(comparable)
    if (kind === 'headers') {
      if (!/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(key)
        || typeof item !== 'string' || /[^\x20-\x7e]/.test(item)) return { error: 'invalid_header' }
    } else if (!(scalar(item) || kind === 'query' && Array.isArray(item) && item.every(scalar))) {
      return { error: kind === 'query' ? 'query_value' : 'form_value' }
    }
  }
  return { value }
}

export function httpValueRows(source, kind) {
  const parsed = parseHttpValue(source, kind)
  if (parsed.error) return parsed
  return { rows: Object.entries(parsed.value).map(([key, value]) => ({
    key, value: typeof value === 'string' ? value : JSON.stringify(value),
    type: typeof value === 'string' ? 'text' : 'json',
  })) }
}

export function serializeHttpRows(rows) {
  return `{${rows.map(row => `${JSON.stringify(row.key)}: ${row.type === 'json' ? row.value : JSON.stringify(row.value)}`).join(',\n')}}`
}

export function validateHttpRequestFields(fields, connected = []) {
  const errors = []
  const check = (name, kind) => {
    if (connected.includes(name)) return
    const result = parseHttpValue(fields[name] ? fields[name].value : name === 'body' ? '' : '{}', kind)
    if (result.error) errors.push({ field: name, error: result.error })
  }
  check('headers', 'headers')
  check('query_params', 'query')
  if (!connected.includes('body_type')) {
    if (fields.body_type?.value === 'form') check('body', 'form')
    if (fields.body_type?.value === 'json') check('body', 'json')
  }
  return errors
}

export function findHttpRequestError(data) {
  const nodes = data.nodes || []
  const edges = data.edges || []
  const ignoredSources = new Set(nodes.filter(node => node.ignored).map(node => node.id))
  for (const node of nodes) {
    if (node.ignored || node.type !== 'HttpRequest') continue
    const fields = node.data?.template || {}
    const connected = Object.keys(fields).filter(key => edges.some(edge => !edge.ignored
      && !ignoredSources.has(edge.source) && edge.target === node.id
      && [key, fields[key].id, fields[key].name].filter(Boolean).includes(edge.targetHandle)))
    const error = validateHttpRequestFields(fields, connected)[0]
    if (error) return { node, ...error }
  }
  return null
}

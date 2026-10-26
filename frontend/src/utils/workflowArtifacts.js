import { getWorkflowTaskTitleKey } from './workflowFailures.js'

export function formatArtifactSize(size) {
  if (!Number.isFinite(size) || size < 0) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export function artifactSourceLabel(source, t, te, categories = ['outputs', 'tools', 'fileProcessing', 'llms']) {
  const taskKey = getWorkflowTaskTitleKey(source.node_type)
  const key = taskKey || categories.map(category => `components.nodes.${category}.${source.node_type}.title`).find(te)
  return source.title || (key && te(key) ? t(key) : source.node_type) || source.node_id
}

export function createRunArtifacts(api, changed) {
  let rid = null, scope = 0, generation = 0, disposed = false
  const state = { artifacts: [], error: '', pending: '' }
  const publish = () => changed({ ...state })
  const current = (id, epoch) => !disposed && rid === id && scope === epoch
  async function refresh() {
    if (!rid || disposed) return
    const id = rid, epoch = scope, request = ++generation
    try {
      const response = await api('list_artifacts', { rid: id })
      if (!current(id, epoch) || request !== generation) return
      if (response.status !== 200) throw new Error('list')
      state.artifacts = Array.isArray(response.data?.artifacts) ? response.data.artifacts : []
      state.error = ''
    } catch {
      if (!current(id, epoch) || request !== generation) return
      state.error = 'list'
    }
    publish()
  }
  return {
    refresh,
    select(id) {
      scope++; generation++; rid = id
      Object.assign(state, { artifacts: [], error: '', pending: '' }); publish()
      return refresh()
    },
    async open(artifact, action) {
      if (!rid || disposed || state.pending || !state.artifacts.includes(artifact)) return
      if (action !== 'open' && action !== 'folder') return
      if (action === 'open' ? !artifact.exists : !artifact.parent_exists) return
      const id = rid, epoch = scope, path = artifact.path
      state.pending = path; state.error = ''; publish()
      try {
        const response = await api('open_artifact', { rid: id, path, action })
        if (!current(id, epoch)) return
        if (response.status !== 200) throw new Error('open')
      } catch {
        if (!current(id, epoch)) return
        await refresh()
        if (!current(id, epoch)) return
        state.error = 'open'
      } finally {
        if (current(id, epoch)) { state.pending = ''; publish() }
      }
    },
    dispose() { disposed = true; scope++; generation++ },
  }
}

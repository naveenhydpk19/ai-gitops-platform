import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import {
  Activity, AlertTriangle, Bot, CheckCircle2, Clock3, ExternalLink, GitBranch,
  GitPullRequest, Network, RefreshCw, Rocket, Search, Send, Server, ShieldCheck,
} from 'lucide-react'
import './changeguard.css'
import './history.css'
import './operational.css'

type View = 'review' | 'dependencies' | 'signals' | 'release'
type Factor = { label: string; points: number; evidence: string }
type CheckRun = { name: string; status: string; conclusion: string | null }
type Source = {
  repository?: string; title?: string; url?: string; head_sha?: string; author?: string
  files?: string[]; check_runs?: CheckRun[]; tests_passed?: boolean; has_rollback_plan?: boolean
}
type Analysis = {
  changeId?: string; analyzedAt?: string; score: number; level: string; decision: string
  factors: Factor[]; affectedServices: string[]; requiredControls: string[]; source?: Source
}
type Service = { name: string; repository: string; paths: string[]; depends_on: string[] }
type Graph = {
  configured: boolean; source: string; services: Service[]; edges: { from: string; to: string }[]
  changedServices?: string[]; impactedServices?: string[]
}
type IntegrationStatus = Record<string, { configured: boolean; supportsPublicWithoutToken?: boolean }>
type Signals = {
  service: string
  prometheus: { configured: boolean; available: boolean; error?: string; metrics?: { errorRate: number | null; requestRate: number | null } }
  rollout: { configured: boolean; available: boolean; error?: string; phase?: string; replicas?: number; updatedReplicas?: number; availableReplicas?: number; currentStepIndex?: number }
}
type DeliveryPlan = {
  planId: string; status: string; repository: string; version: string; changeRequest?: number
  model: string; blockers: string[]
  intent: { action: string; branch: string; environments: string[]; summary: string }
  agents: { agent: string; decision: string; reasons: string[] }[]
  steps: { id: string; label: string; control: string }[]
  execution?: { accepted: boolean; actionsUrl: string }
}

async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)
  const body = await response.text()
  let data: unknown

  try {
    data = body ? JSON.parse(body) : null
  } catch {
    throw new Error(`ChangeGuard API returned an invalid response (${response.status})`)
  }

  if (!response.ok) {
    const detail = data && typeof data === 'object' && 'detail' in data
      ? String(data.detail)
      : `Request failed (${response.status})`
    throw new Error(detail)
  }
  if (data === null) throw new Error(`ChangeGuard API returned an empty response (${response.status})`)
  return data as T
}

function verificationStatus(source: Source | null) {
  const checks = source?.check_runs ?? []
  if (checks.length === 0) return { label: 'No checks reported', passing: false }
  if (source?.tests_passed) return { label: 'Passing', passing: true }
  if (checks.some(check => check.status !== 'completed')) return { label: 'Pending', passing: false }
  return { label: 'Failing', passing: false }
}

function App() {
  const [view, setView] = useState<View>('review')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [source, setSource] = useState<Source | null>(null)
  const [history, setHistory] = useState<Analysis[]>([])
  const [graph, setGraph] = useState<Graph | null>(null)
  const [integrations, setIntegrations] = useState<IntegrationStatus | null>(null)
  const [signals, setSignals] = useState<Signals | null>(null)
  const [deliveryPlan, setDeliveryPlan] = useState<DeliveryPlan | null>(null)
  const [deliveryRequest, setDeliveryRequest] = useState('I merged the changes in master. Create a tag and release, then deploy to dev, qa, and prod.')
  const [deliveryRepository, setDeliveryRepository] = useState('naveenhydpk19/ai-gitops-platform')
  const [releaseVersion, setReleaseVersion] = useState('1.0.0')
  const [changeRequest, setChangeRequest] = useState('')
  const [repository, setRepository] = useState('')
  const [pullRequest, setPullRequest] = useState('')
  const [service, setService] = useState('gateway-svc')
  const [namespace, setNamespace] = useState('dev')
  const [rollout, setRollout] = useState('gateway-svc')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    void Promise.all([
      api<{ items: Analysis[] }>('/api/v1/changes?limit=8'),
      api<Graph>('/api/v1/dependencies'),
      api<IntegrationStatus>('/api/v1/integrations/status'),
    ]).then(([changes, dependencyGraph, status]) => {
      setHistory(changes.items)
      setGraph(dependencyGraph)
      setIntegrations(status)
    }).catch(() => setError('The ChangeGuard API is unavailable.'))
  }, [])

  const importPullRequest = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const imported = await api<{ source: Source; impact: Graph; analysis: Analysis }>(
        '/api/v1/integrations/github/import',
        {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ repository, pull_request: Number(pullRequest) }),
        },
      )
      setSource(imported.source)
      setAnalysis(imported.analysis)
      setGraph(imported.impact)
      setHistory((await api<{ items: Analysis[] }>('/api/v1/changes?limit=8')).items)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'GitHub import failed')
    } finally {
      setBusy(false)
    }
  }

  const loadSignals = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      setSignals(await api<Signals>(`/api/v1/rollouts/signals?service=${encodeURIComponent(service)}&namespace=${encodeURIComponent(namespace)}&rollout=${encodeURIComponent(rollout)}`))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Signal query failed')
    } finally {
      setBusy(false)
    }
  }

  const planDelivery = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      setDeliveryPlan(await api<DeliveryPlan>('/api/v1/delivery/plan', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: deliveryRequest,
          repository: deliveryRepository,
          version: releaseVersion,
          change_request: changeRequest ? Number(changeRequest) : null,
        }),
      }))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Delivery planning failed')
    } finally {
      setBusy(false)
    }
  }

  const executeDelivery = async () => {
    if (!deliveryPlan) return
    setBusy(true)
    setError('')
    try {
      setDeliveryPlan(await api<DeliveryPlan>(`/api/v1/delivery/plans/${deliveryPlan.planId}/execute`, { method: 'POST' }))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Workflow dispatch failed')
    } finally {
      setBusy(false)
    }
  }

  const selectHistory = (item: Analysis) => {
    setAnalysis(item)
    setSource(item.source ?? null)
    setView('review')
  }

  const blocked = analysis?.decision === 'BLOCKED_PENDING_CONTROLS'
  const verification = verificationStatus(source)

  return <div className="shell">
    <aside>
      <div className="brand"><ShieldCheck size={24}/><strong>ChangeGuard</strong></div>
      <p className="eyebrow">Production change control</p>
      <nav>
        <button className={view === 'review' ? 'active' : ''} onClick={() => setView('review')}><GitPullRequest size={18}/>Change review</button>
        <button className={view === 'dependencies' ? 'active' : ''} onClick={() => setView('dependencies')}><Network size={18}/>Dependencies</button>
        <button className={view === 'signals' ? 'active' : ''} onClick={() => setView('signals')}><Activity size={18}/>Rollout signals</button>
        <button className={view === 'release' ? 'active' : ''} onClick={() => setView('release')}><Bot size={18}/>AI Release Ops</button>
      </nav>
      <div className="policy-status"><span/><div><strong>Policy engine online</strong><small>Deterministic decisions</small></div></div>
    </aside>

    <main>
      {error && <div className="error-banner"><AlertTriangle size={18}/>{error}<button onClick={() => setError('')}>Dismiss</button></div>}

      {view === 'review' && <>
        <header><div><p className="eyebrow">GitHub evidence / {analysis?.changeId ?? 'No PR selected'}</p><h1>Production change review</h1></div></header>
        <form className="command-bar" onSubmit={importPullRequest}>
          <label><span>Repository</span><input value={repository} onChange={event => setRepository(event.target.value)} placeholder="owner/repository" required pattern=".+/.+"/></label>
          <label className="pr-input"><span>Pull request</span><input type="number" min="1" value={pullRequest} onChange={event => setPullRequest(event.target.value)} placeholder="42" required/></label>
          <button className="analyze" disabled={busy}><Search size={17}/>{busy ? 'Importing...' : 'Import from GitHub'}</button>
          <div className={`source-state ${integrations?.github?.configured ? 'connected' : ''}`}><GitBranch size={16}/><span>{integrations?.github?.configured ? 'Authenticated API' : 'Public API mode'}</span></div>
        </form>

        {!analysis && <section className="empty-workspace"><GitPullRequest size={34}/><h2>No change has been analyzed</h2><p>Enter a real GitHub repository and pull request. ChangeGuard fetches changed files and check runs directly from GitHub before applying policy.</p></section>}

        {analysis && <>
          <section className={`decision-strip ${blocked ? '' : 'ready'}`}>
            <div className="risk-score"><span>{analysis.score}</span><div><strong>{analysis.level} RISK</strong><small>out of 100</small></div></div>
            <div className="decision">{blocked ? <AlertTriangle size={22}/> : <CheckCircle2 size={22}/>}<div><strong>{blocked ? 'Deployment blocked pending controls' : 'Ready for controlled canary'}</strong><small>{blocked ? 'Required evidence is missing or checks have failed.' : 'Policy checks passed. Begin monitored rollout.'}</small></div></div>
            <div className="commit"><small>Evidence source</small><strong>{source?.repository ?? 'Persisted analysis'}</strong><code>{source?.head_sha?.slice(0, 8) ?? analysis.changeId}</code></div>
          </section>
          <div className="grid">
            <section className="panel"><div className="panel-head"><div><p className="eyebrow">GitHub change set</p><h2>{source?.title ?? analysis.changeId}</h2></div>{source?.url && <a className="icon-link" href={source.url} target="_blank" rel="noreferrer" title="Open pull request"><ExternalLink size={17}/></a>}</div><p className="summary">Author: {source?.author ?? 'unknown'} · Commit: {source?.head_sha?.slice(0, 8) ?? 'not recorded'}</p>{source?.files?.length ? source.files.map(file => <div className="file" key={file}><code>{file}</code></div>) : <p className="muted">File evidence was not recorded for this analysis.</p>}</section>
            <section className="panel"><div className="panel-head"><div><p className="eyebrow">Explainable score</p><h2>Risk factors</h2></div><strong>{analysis.score} pts</strong></div>{analysis.factors.length ? analysis.factors.map(factor => <div className="factor" key={factor.label}><span>+{factor.points}</span><div><strong>{factor.label}</strong><small>{factor.evidence}</small></div></div>) : <p className="muted">No elevated risk patterns detected.</p>}</section>
            <section className="panel"><div className="panel-head"><div><p className="eyebrow">GitHub checks</p><h2>Verification evidence</h2></div><span className={`pill ${verification.passing ? '' : 'danger'}`}>{verification.label}</span></div>{source?.check_runs?.length ? source.check_runs.map(check => <div className="check-row" key={check.name}><strong>{check.name}</strong><span>{check.status}</span><small>{check.conclusion ?? 'pending'}</small></div>) : <p className="muted">GitHub returned no check runs for this commit. Policy treats missing evidence as not passing.</p>}</section>
            <section className="panel"><div className="panel-head"><div><p className="eyebrow">Deterministic policy</p><h2>Required controls</h2></div><span className="pill danger">{analysis.requiredControls.length} controls</span></div>{analysis.requiredControls.map((control, index) => <div className="control" key={control}><span>{index + 1}</span><strong>{control}</strong><small>Required</small></div>)}</section>
          </div>
        </>}

        <section className="history-panel"><div className="panel-head"><div><p className="eyebrow">Audit trail</p><h2>Persisted decisions</h2></div><Clock3 size={19}/></div>{history.length === 0 && <p className="history-state">No persisted decisions.</p>}{history.map(item => <button className="history-row" key={item.changeId} onClick={() => selectHistory(item)}><strong>{item.changeId}</strong><span className={`risk-tag ${item.level.toLowerCase()}`}>{item.level}</span><span>{item.score} pts</span><span className={item.decision === 'READY_FOR_CANARY' ? 'status-ready' : 'status-blocked'}>{item.decision === 'READY_FOR_CANARY' ? 'Canary ready' : 'Blocked'}</span><time>{item.analyzedAt ? new Date(`${item.analyzedAt}Z`).toLocaleString() : 'Unknown'}</time></button>)}</section>
      </>}

      {view === 'dependencies' && <>
        <header><div><p className="eyebrow">Service catalog / impact analysis</p><h1>Dependencies</h1></div><span className={`connection-chip ${graph?.configured ? 'connected' : ''}`}><Server size={16}/>{graph?.configured ? 'Catalog loaded' : 'Catalog missing'}</span></header>
        <section className="source-note"><strong>Source of truth</strong><code>{graph?.source ?? 'Loading...'}</code><span>{graph?.services.length ?? 0} services · {graph?.edges.length ?? 0} dependency edges</span></section>
        {!graph?.configured ? <section className="empty-workspace"><Network size={34}/><h2>No service catalog configured</h2><p>Set <code>SERVICE_CATALOG_PATH</code> to a versioned catalog file.</p></section> : <>
          <section className="dependency-grid">{graph.services.map(item => { const changed = graph.changedServices?.includes(item.name); const impacted = graph.impactedServices?.includes(item.name); return <article className={`service-node ${changed ? 'changed' : impacted ? 'impacted' : ''}`} key={item.name}><div><Server size={18}/><strong>{item.name}</strong></div><small>{item.repository}</small><span>{changed ? 'Changed by selected PR' : impacted ? 'Downstream impact' : 'Catalog service'}</span></article> })}</section>
          <section className="edge-list"><div className="panel-head"><div><p className="eyebrow">Runtime relationships</p><h2>Dependency edges</h2></div><Network size={19}/></div>{graph.edges.map(edge => <div className="edge-row" key={`${edge.from}-${edge.to}`}><strong>{edge.from}</strong><span>depends on</span><strong>{edge.to}</strong></div>)}</section>
        </>}
      </>}

      {view === 'signals' && <>
        <header><div><p className="eyebrow">Prometheus + Argo Rollouts</p><h1>Rollout signals</h1></div><RefreshCw size={20}/></header>
        <div className="connector-grid"><article><span className={integrations?.prometheus?.configured ? 'online' : ''}/><div><strong>Prometheus</strong><small>{integrations?.prometheus?.configured ? 'Endpoint configured' : 'PROMETHEUS_URL not configured'}</small></div></article><article><span className={integrations?.argoRollouts?.configured ? 'online' : ''}/><div><strong>Argo Rollouts</strong><small>{integrations?.argoRollouts?.configured ? 'Kubernetes API configured' : 'Kubernetes credentials not configured'}</small></div></article></div>
        <form className="command-bar signal-form" onSubmit={loadSignals}><label><span>Service label</span><input value={service} onChange={event => setService(event.target.value)} required/></label><label><span>Namespace</span><input value={namespace} onChange={event => setNamespace(event.target.value)} required/></label><label><span>Rollout resource</span><input value={rollout} onChange={event => setRollout(event.target.value)} required/></label><button className="analyze" disabled={busy}><Activity size={17}/>{busy ? 'Querying...' : 'Query live signals'}</button></form>
        {!signals && <section className="empty-workspace"><Activity size={34}/><h2>No environment query has run</h2><p>Configure the connectors, then query a service and Argo Rollout resource. ChangeGuard does not synthesize metrics when a source is absent.</p></section>}
        {signals && <div className="signal-results"><article><p className="eyebrow">5xx error rate</p><strong>{signals.prometheus.metrics?.errorRate != null ? `${signals.prometheus.metrics.errorRate.toFixed(2)}%` : 'No data'}</strong><small>{signals.prometheus.metrics?.errorRate != null ? 'Live Prometheus query' : signals.prometheus.available ? 'No matching Prometheus series' : signals.prometheus.error ?? 'Connector not configured'}</small></article><article><p className="eyebrow">Request rate</p><strong>{signals.prometheus.metrics?.requestRate != null ? `${signals.prometheus.metrics.requestRate.toFixed(1)}/s` : 'No data'}</strong><small>{signals.prometheus.metrics?.requestRate != null ? 'Live Prometheus query' : signals.prometheus.available ? 'No matching Prometheus series' : signals.prometheus.error ?? 'Connector not configured'}</small></article><article><p className="eyebrow">Rollout phase</p><strong>{signals.rollout.phase ?? 'Not deployed'}</strong><small>{signals.rollout.available ? `${signals.rollout.updatedReplicas ?? 0}/${signals.rollout.replicas ?? 0} replicas updated` : signals.rollout.error ?? 'Connector not configured'}</small></article></div>}
      </>}

      {view === 'release' && <>
        <header><div><p className="eyebrow">LangChain multi-agent control plane</p><h1>AI Release Ops</h1></div><span className={`connection-chip ${integrations?.openai?.configured ? 'connected' : ''}`}><Bot size={16}/>{integrations?.openai?.configured ? 'gpt-4o-mini connected' : 'OpenAI not configured'}</span></header>
        <section className="release-layout">
          <form className="release-request" onSubmit={planDelivery}>
            <div className="panel-head"><div><p className="eyebrow">Developer request</p><h2>Plan a governed release</h2></div><Send size={18}/></div>
            <label><span>Request</span><textarea value={deliveryRequest} onChange={event => setDeliveryRequest(event.target.value)} rows={5} required/></label>
            <div className="release-fields"><label><span>GitHub repository</span><input value={deliveryRepository} onChange={event => setDeliveryRepository(event.target.value)} pattern=".+/.+" required/></label><label><span>Semantic version</span><input value={releaseVersion} onChange={event => setReleaseVersion(event.target.value)} pattern="v?[0-9]+\.[0-9]+\.[0-9]+" required/></label><label><span>Change request issue</span><input type="number" min="1" value={changeRequest} onChange={event => setChangeRequest(event.target.value)} placeholder="Required for prod"/></label></div>
            <button className="analyze" disabled={busy || !integrations?.openai?.configured}><Bot size={17}/>{busy ? 'Agents working...' : 'Generate deployment plan'}</button>
            {!integrations?.openai?.configured && <p className="configuration-note">Set <code>OPENAI_API_KEY</code> on the backend to enable planning. The model proposes; deterministic policy controls execution.</p>}
          </form>

          {!deliveryPlan && <section className="empty-workspace release-empty"><Rocket size={34}/><h2>No release plan generated</h2><p>Release Intent, Release Review, and Production Policy agents will independently inspect the request before the deterministic supervisor allows execution.</p></section>}

          {deliveryPlan && <section className="delivery-plan">
            <div className="plan-summary"><div><p className="eyebrow">Plan {deliveryPlan.planId.slice(0, 8)}</p><h2>{deliveryPlan.intent.summary}</h2><span>{deliveryPlan.repository} · v{deliveryPlan.version} · {deliveryPlan.intent.branch}</span></div><strong className={deliveryPlan.status === 'READY_FOR_EXECUTION' ? 'status-ready' : 'status-blocked'}>{deliveryPlan.status.replaceAll('_', ' ')}</strong></div>
            {deliveryPlan.blockers.length > 0 && <div className="plan-blockers">{deliveryPlan.blockers.map(blocker => <p key={blocker}><AlertTriangle size={15}/>{blocker}</p>)}</div>}
            <div className="agent-opinions">{deliveryPlan.agents.map((agent, index) => <article key={`${agent.agent}-${index}`}><div><Bot size={17}/><strong>{agent.agent}</strong><span className={agent.decision === 'allow' ? 'status-ready' : 'status-blocked'}>{agent.decision}</span></div>{agent.reasons.map(reason => <p key={reason}>{reason}</p>)}</article>)}</div>
            <div className="deployment-steps">{deliveryPlan.steps.map((step, index) => <div key={step.id}><span>{index + 1}</span><div><strong>{step.label}</strong><small>{step.control}</small></div></div>)}</div>
            <div className="execute-bar"><div><strong>Execution remains deterministic</strong><small>Production revalidates the change-approved issue before GitHub Actions dispatch.</small></div><button className="analyze" onClick={executeDelivery} disabled={busy || deliveryPlan.status !== 'READY_FOR_EXECUTION'}><Rocket size={17}/>{deliveryPlan.execution ? 'Workflow dispatched' : 'Execute approved plan'}</button></div>
            {deliveryPlan.execution?.actionsUrl && <a className="workflow-link" href={deliveryPlan.execution.actionsUrl} target="_blank" rel="noreferrer">Open GitHub Actions <ExternalLink size={15}/></a>}
          </section>}
        </section>
      </>}
    </main>
  </div>
}

export default App
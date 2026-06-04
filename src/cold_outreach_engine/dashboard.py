from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cold_outreach_engine.agents.icp_planner import IcpPlannerAgent
from cold_outreach_engine.config import load_settings
from cold_outreach_engine.models import to_jsonable, utc_now
from cold_outreach_engine.orchestrator import LeadGenerationOrchestrator
from cold_outreach_engine.providers.factory import build_crawl_provider, build_search_provider
from cold_outreach_engine.storage import JsonStore


HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tyvexa Outreach Engine</title>
  <style>
    :root {
      --bg: #070809;
      --panel: rgba(16, 18, 20, .86);
      --panel-2: rgba(22, 24, 27, .72);
      --line: rgba(255, 255, 255, .13);
      --line-strong: rgba(255, 255, 255, .24);
      --text: #f2f2ef;
      --muted: #8c908e;
      --dim: #5f6462;
      --accent: #f4f4ef;
      --good: #b8ffda;
      --warn: #ffe2a8;
      --bad: #ffb4b4;
      --mono: "SFMono-Regular", "SF Mono", Menlo, Consolas, monospace;
      --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px),
        radial-gradient(circle at 74% 18%, rgba(255,255,255,.12), transparent 24%),
        var(--bg);
      background-size: 96px 96px, 96px 96px, auto, auto;
      color: var(--text);
      font-family: var(--sans);
      overflow: hidden;
    }

    .shell { height: 100vh; display: grid; grid-template-rows: 74px 1fr; }
    .topbar {
      display: grid;
      grid-template-columns: 260px 1fr 440px;
      align-items: center;
      border-bottom: 1px solid var(--line-strong);
      background: rgba(7, 8, 9, .86);
    }
    .brand { padding: 0 28px; display: flex; align-items: center; gap: 14px; }
    .brand-mark { font-family: var(--mono); font-size: 23px; font-weight: 700; transform: rotate(90deg); }
    .brand-name { font-family: var(--mono); letter-spacing: .34em; font-size: 15px; font-weight: 700; }
    .agent-pill {
      justify-self: center;
      min-width: 330px;
      border: 1px solid var(--line-strong);
      border-radius: 999px;
      padding: 10px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: rgba(255,255,255,.035);
      box-shadow: inset 0 0 22px rgba(255,255,255,.025);
    }
    .agent-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--good); box-shadow: 0 0 18px var(--good); }
    .agent-copy { display: grid; gap: 3px; }
    .micro { font-family: var(--mono); font-size: 10px; text-transform: uppercase; letter-spacing: .16em; color: var(--muted); }
    .agent-title { font-family: var(--mono); font-size: 12px; text-transform: uppercase; letter-spacing: .12em; }
    .nav { display: flex; justify-content: flex-end; gap: 36px; padding-right: 30px; }
    .nav span { font-family: var(--mono); font-size: 11px; text-transform: uppercase; letter-spacing: .22em; color: #c8cbc8; }

    .workspace {
      display: grid;
      grid-template-columns: 300px minmax(560px, 1fr) 430px;
      height: calc(100vh - 74px);
      border-left: 1px solid var(--line);
    }
    aside, main, .drawer { min-height: 0; overflow: auto; }
    aside, .drawer { background: rgba(9, 10, 11, .58); }
    aside { border-right: 1px solid var(--line); }
    main { border-right: 1px solid var(--line); }
    .panel { border-bottom: 1px solid var(--line); padding: 18px; }
    .panel.tight { padding: 14px 18px; }
    .panel-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
    }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: clamp(34px, 4vw, 66px); line-height: .92; text-transform: uppercase; letter-spacing: 0; }
    h2 { font-size: 15px; font-family: var(--mono); text-transform: uppercase; letter-spacing: .14em; }
    h3 { font-size: 16px; line-height: 1.15; }
    .muted { color: var(--muted); }
    .dim { color: var(--dim); }

    textarea, input, select {
      width: 100%;
      background: rgba(255,255,255,.035);
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 8px;
      font: 13px/1.45 var(--mono);
      padding: 12px;
      outline: none;
    }
    textarea:focus, select:focus { border-color: rgba(255,255,255,.44); }
    textarea { min-height: 118px; resize: vertical; }
    button {
      border: 1px solid var(--line-strong);
      background: rgba(255,255,255,.04);
      color: var(--text);
      border-radius: 999px;
      padding: 10px 15px;
      font: 11px var(--mono);
      text-transform: uppercase;
      letter-spacing: .14em;
      cursor: pointer;
    }
    button.primary { background: var(--accent); color: #070809; border-color: var(--accent); }
    button:hover { border-color: rgba(255,255,255,.58); }
    .actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }

    .stat-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
    .stat {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: rgba(255,255,255,.025);
    }
    .stat b { display: block; font-size: 23px; margin-bottom: 4px; }

    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 5px 9px;
      border-radius: 999px;
      border: 1px solid var(--line);
      font: 10px var(--mono);
      text-transform: uppercase;
      letter-spacing: .12em;
      color: #d9ddda;
      white-space: nowrap;
    }
    .status-pill::before {
      content: "";
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--muted);
    }
    .status-qualified::before { background: var(--good); }
    .status-rejected::before { background: var(--bad); }
    .status-manual_review::before, .status-needs_input::before { background: var(--warn); }

    .filters { display: flex; gap: 8px; flex-wrap: wrap; }
    .filter {
      padding: 7px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      font: 10px var(--mono);
      text-transform: uppercase;
      letter-spacing: .12em;
      color: var(--muted);
      cursor: pointer;
    }
    .filter.active { color: #070809; background: var(--accent); border-color: var(--accent); }

    .lead-table { display: grid; }
    .lead-row {
      display: grid;
      grid-template-columns: minmax(190px, 1.6fr) 96px 92px 128px 126px;
      gap: 14px;
      align-items: center;
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
      cursor: pointer;
      background: rgba(255,255,255,.01);
    }
    .lead-row:hover, .lead-row.active { background: rgba(255,255,255,.06); }
    .lead-row.header {
      position: sticky;
      top: 0;
      z-index: 2;
      background: rgba(7,8,9,.96);
      color: var(--muted);
      font: 10px var(--mono);
      text-transform: uppercase;
      letter-spacing: .14em;
      cursor: default;
    }
    .score { font-family: var(--mono); font-size: 19px; }
    .copy { font-size: 13px; line-height: 1.45; color: #d6dad6; }
    .url { color: var(--muted); font: 11px var(--mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

    .drawer-empty {
      height: 100%;
      display: grid;
      place-items: center;
      padding: 30px;
      text-align: center;
      color: var(--muted);
    }
    .detail-head { padding: 22px; border-bottom: 1px solid var(--line); }
    .detail-head h2 { font-size: 24px; font-family: var(--sans); letter-spacing: 0; text-transform: none; margin-top: 10px; }
    .detail-block { padding: 18px 22px; border-bottom: 1px solid var(--line); }
    .detail-block > .micro { margin-bottom: 10px; }
    .claim {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px;
      margin-bottom: 9px;
      background: rgba(255,255,255,.025);
    }
    .claim .micro { margin-top: 7px; }
    details {
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-top: 10px;
      background: rgba(255,255,255,.02);
    }
    summary { cursor: pointer; padding: 11px; font: 11px var(--mono); text-transform: uppercase; letter-spacing: .12em; }
    pre {
      max-height: 280px;
      overflow: auto;
      white-space: pre-wrap;
      color: #cfd3cf;
      font: 11px/1.45 var(--mono);
      margin: 0;
      padding: 12px;
      border-top: 1px solid var(--line);
    }
    .progress-slot {
      border: 1px dashed rgba(255,255,255,.28);
      border-radius: 8px;
      padding: 14px;
      background: rgba(255,255,255,.02);
    }
    .error {
      border-color: rgba(255,180,180,.36);
      color: var(--bad);
    }
    .list-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px;
      margin-bottom: 9px;
      background: rgba(255,255,255,.025);
    }
    .run-status { margin-top: 10px; min-height: 18px; }

    @media (max-width: 1180px) {
      body { overflow: auto; }
      .shell { height: auto; min-height: 100vh; }
      .topbar { grid-template-columns: 1fr; gap: 14px; padding: 16px; }
      .brand, .nav { padding: 0; }
      .agent-pill { justify-self: stretch; min-width: 0; }
      .workspace { grid-template-columns: 1fr; height: auto; }
      .lead-row { grid-template-columns: 1fr; }
      .lead-row.header { display: none; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">T</div>
        <div class="brand-name">TYVEXA</div>
      </div>
      <div class="agent-pill">
        <div class="agent-copy">
          <span class="micro">Tyvexa Agent</span>
          <span class="agent-title">Outreach Engine Active</span>
        </div>
        <span class="agent-dot"></span>
      </div>
      <nav class="nav">
        <span>Leads</span>
        <span>Signals</span>
        <span>Progress</span>
      </nav>
    </header>

    <div class="workspace">
      <aside>
        <section class="panel">
          <div class="panel-title">
            <h2>Campaign Console</h2>
            <span class="micro">Prompt / Run</span>
          </div>
          <form onsubmit="runCampaign(event)">
            <textarea name="prompt">Find me leads in Finland for restaurant businesses looking for voice AI capabilities</textarea>
            <div class="actions">
              <button type="button" onclick="planCampaign()">Plan Only</button>
              <button class="primary">Run Capped</button>
            </div>
            <div id="run-status" class="micro run-status"></div>
          </form>
        </section>

        <section class="panel tight">
          <div class="panel-title">
            <h2>Provider Health</h2>
            <span class="micro" id="provider-count">00</span>
          </div>
          <div id="providers"></div>
        </section>

        <section class="panel tight">
          <div class="panel-title">
            <h2>Campaigns</h2>
            <span class="micro" id="campaign-count">00</span>
          </div>
          <div id="campaigns"></div>
        </section>

        <section class="panel tight">
          <div class="panel-title">
            <h2>Open Questions</h2>
            <span class="micro" id="question-count">00</span>
          </div>
          <div id="questions"></div>
        </section>
      </aside>

      <main>
        <section class="panel">
          <div class="micro">Tyvexa / Lead Generation</div>
          <h1>Lead Command Center</h1>
          <p class="copy muted" style="max-width: 680px; margin-top: 16px;">Scan qualified targets, inspect evidence, review bulky source data, and keep a clean slot for lead progress once the outreach workflow lands.</p>
        </section>
        <section class="panel tight">
          <div class="stat-grid" id="stats"></div>
        </section>
        <section class="panel tight">
          <div class="panel-title">
            <h2>Lead Dossiers</h2>
            <span class="micro" id="lead-count">00</span>
          </div>
          <div class="filters" id="filters"></div>
        </section>
        <section class="lead-table" id="lead-table"></section>
      </main>

      <aside class="drawer" id="drawer"></aside>
    </div>
  </div>

  <script>
    const stages = ['new','linkedin_searched','contacted','follow_up_due','replied','not_fit','won','lost'];
    const filters = ['all','qualified','manual_review','needs_input','rejected'];
    let state = { campaigns: [], dossiers: [], clarifications: [], provider_errors: [], leads: [], scores: [], buyer_signals: [], solution_assessments: [], source_plans: [], settings: {} };
    let activeFilter = 'all';
    let selectedCampaignId = null;
    let selectedId = null;

    const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    const short = (value, max = 42) => {
      const text = String(value ?? '');
      return text.length > max ? text.slice(0, max - 1) + '…' : text;
    };
    const fmt = n => String(n).padStart(2, '0');

    async function load() {
      const data = await fetch('/api/state').then(r => r.json());
      state = data;
      const campaignIds = state.campaigns.map(c => c.id);
      if (!selectedCampaignId || !campaignIds.includes(selectedCampaignId)) {
        selectedCampaignId = state.campaigns.length ? state.campaigns[state.campaigns.length - 1].id : null;
      }
      const visible = filteredDossiers();
      if (!selectedId || !visible.some(d => d.id === selectedId)) {
        selectedId = visible.length ? visible[0].id : null;
      }
      render();
    }

    function render() {
      renderProviders();
      renderCampaigns();
      renderQuestions();
      renderStats();
      renderFilters();
      renderLeads();
      renderDrawer();
    }

    function renderProviders() {
      const providers = state.settings.active_search_providers || [];
      const crawl = state.settings.active_crawl_provider;
      const recentErrors = state.provider_errors
        .filter(e => !selectedCampaignId || e.campaign_id === selectedCampaignId)
        .slice(-4)
        .reverse();
      document.querySelector('#provider-count').textContent = fmt(providers.length + (crawl ? 1 : 0));
      document.querySelector('#providers').innerHTML = `
        ${providers.map(p => `<div class="list-card"><span class="status-pill status-qualified">${esc(p)}</span><div class="micro" style="margin-top:8px;">Search provider</div></div>`).join('')}
        ${crawl ? `<div class="list-card"><span class="status-pill status-qualified">${esc(crawl)}</span><div class="micro" style="margin-top:8px;">Crawl provider</div></div>` : ''}
        <div class="list-card"><div class="micro">Caps</div><div class="copy">${esc(state.settings.max_candidates_per_run)} candidates / ${esc(state.settings.max_deep_analysis_per_run)} deep analyses</div></div>
        ${recentErrors.map(e => `<div class="list-card error"><div class="micro">${esc(e.provider)} / ${esc(e.status_code || 'ERR')}</div><div class="copy">${esc(short(e.message, 180))}</div></div>`).join('')}
        ${recentErrors.length ? '' : '<div class="list-card"><div class="micro">Selected run</div><div class="copy">No provider errors captured.</div></div>'}
      `;
    }

    function renderCampaigns() {
      const latest = state.campaigns.slice(-5).reverse();
      document.querySelector('#campaign-count').textContent = fmt(state.campaigns.length);
      document.querySelector('#campaigns').innerHTML = latest.map(c =>
        `<div class="list-card" onclick="selectCampaign('${c.id}')" style="${selectedCampaignId === c.id ? 'border-color: rgba(255,255,255,.58);' : ''}"><h3>${esc(c.offer)}</h3><div class="micro" style="margin-top:8px;">${esc((c.countries || []).join(', '))} / ${esc((c.industries || []).join(', '))}</div></div>`
      ).join('') || '<div class="micro">No campaigns yet.</div>';
    }

    function renderQuestions() {
      const open = state.clarifications.filter(q => q.status === 'open' && (!selectedCampaignId || q.campaign_id === selectedCampaignId)).slice(-4).reverse();
      document.querySelector('#question-count').textContent = fmt(open.length);
      document.querySelector('#questions').innerHTML = open.map(q =>
        `<div class="list-card"><span class="status-pill status-needs_input">${esc(q.scope)}</span><p class="copy" style="margin-top:10px;">${esc(q.question)}</p></div>`
      ).join('') || '<div class="micro">No open questions.</div>';
    }

    function renderStats() {
      const counts = currentCampaignDossiers().reduce((acc, d) => { acc[d.status] = (acc[d.status] || 0) + 1; return acc; }, {});
      const qualified = counts.qualified || 0;
      const review = (counts.manual_review || 0) + (counts.needs_input || 0);
      const rejected = counts.rejected || 0;
      const errors = state.provider_errors.filter(e => !selectedCampaignId || e.campaign_id === selectedCampaignId).length;
      document.querySelector('#stats').innerHTML = [
        ['Qualified', qualified],
        ['Review', review],
        ['Rejected', rejected],
        ['Provider Errors', errors],
      ].map(([label, value]) => `<div class="stat"><b>${fmt(value)}</b><span class="micro">${label}</span></div>`).join('');
    }

    function renderFilters() {
      document.querySelector('#filters').innerHTML = filters.map(f =>
        `<div class="filter ${activeFilter === f ? 'active' : ''}" onclick="setFilter('${f}')">${f}</div>`
      ).join('');
    }

    function filteredDossiers() {
      return currentCampaignDossiers()
        .filter(d => activeFilter === 'all' || d.status === activeFilter)
        .slice()
        .reverse();
    }

    function currentCampaignDossiers() {
      if (!selectedCampaignId) return state.dossiers;
      return state.dossiers.filter(d => d.campaign_id === selectedCampaignId);
    }

    function renderLeads() {
      const rows = filteredDossiers();
      document.querySelector('#lead-count').textContent = fmt(rows.length);
      document.querySelector('#lead-table').innerHTML = `
        <div class="lead-row header"><span>Company</span><span>Status</span><span>Score</span><span>Solution</span><span>Progress</span></div>
        ${rows.map(d => `
          <div class="lead-row ${selectedId === d.id ? 'active' : ''}" onclick="selectLead('${d.id}')">
            <div>
              <h3>${esc(d.company_name)}</h3>
              <div class="url">${esc((leadFor(d.lead_id) || {}).website || 'no website captured')}</div>
            </div>
            <span class="status-pill status-${esc(d.status)}">${esc(d.status)}</span>
            <span class="score">${esc(d.score)}</span>
            <span class="micro">${esc(short(d.solution_assessment, 30))}</span>
            <span class="micro">${esc(d.follow_up_stage)}</span>
          </div>
        `).join('') || '<div class="panel"><div class="micro">No leads match this filter.</div></div>'}
      `;
    }

    function renderDrawer() {
      const visible = filteredDossiers();
      const d = visible.find(item => item.id === selectedId) || visible[0];
      if (!d) {
        document.querySelector('#drawer').innerHTML = '<div class="drawer-empty"><div><h2>No Lead Selected</h2><p class="copy muted" style="margin-top:10px;">Run a campaign or select a lead dossier.</p></div></div>';
        return;
      }
      selectedId = d.id;
      const lead = leadFor(d.lead_id) || {};
      const score = scoreFor(d.lead_id) || {};
      const signals = state.buyer_signals.filter(s => s.lead_id === d.lead_id);
      const solution = state.solution_assessments.find(s => s.lead_id === d.lead_id);
      document.querySelector('#drawer').innerHTML = `
        <div class="detail-head">
          <span class="status-pill status-${esc(d.status)}">${esc(d.status)}</span>
          <h2>${esc(d.company_name)}</h2>
          <div class="url" style="margin-top:10px;">${esc(lead.website || 'no website captured')}</div>
        </div>
        <div class="detail-block">
          <div class="micro">Lead Progress Drop-In</div>
          <div class="progress-slot">
            <div class="copy"><b>Stage:</b> ${esc(d.follow_up_stage)}</div>
            <div class="micro" style="margin-top:8px;">Reserved module: owner, next action, notes, tags, timeline</div>
            <form onsubmit="updateStage(event, '${d.id}')" style="margin-top:12px;">
              <select name="stage">${stages.map(s => `<option ${s === d.follow_up_stage ? 'selected' : ''}>${s}</option>`).join('')}</select>
              <div class="actions"><button>Update Stage</button></div>
            </form>
          </div>
        </div>
        <div class="detail-block">
          <div class="micro">Outreach Angle</div>
          <p class="copy">${esc(d.manual_opening_message)}</p>
          <details><summary>LinkedIn Manual Search</summary><pre>${esc(d.linkedin_search_hint + '\\n\\nPersona: ' + d.linkedin_persona)}</pre></details>
        </div>
        <div class="detail-block">
          <div class="micro">Evidence-Linked Claims</div>
          ${(d.claims || []).map(c => `<div class="claim"><div class="copy">${esc(c.text)}</div><div class="micro">Confidence ${esc(c.confidence)} / Evidence ${esc((c.evidence_ids || []).join(', ') || 'unknown')}</div></div>`).join('') || '<div class="micro">No claims captured.</div>'}
        </div>
        <div class="detail-block">
          <div class="micro">Buyer Signals</div>
          ${signals.map(s => `<div class="claim"><div class="copy">${esc(s.name)} / strength ${esc(s.strength)}</div><div class="micro">${esc(s.reason)}</div></div>`).join('') || '<div class="micro">No buyer signals captured.</div>'}
        </div>
        <div class="detail-block">
          <div class="micro">Existing Solution</div>
          <p class="copy">${esc(d.solution_assessment)}</p>
          ${solution ? `<details><summary>Solution Raw</summary><pre>${esc(JSON.stringify(solution, null, 2))}</pre></details>` : ''}
        </div>
        <div class="detail-block">
          <div class="micro">Bulky Data</div>
          <details><summary>Score Rubric</summary><pre>${esc(JSON.stringify(score, null, 2))}</pre></details>
          <details><summary>Lead Memory</summary><pre>${esc(JSON.stringify(lead, null, 2))}</pre></details>
          <details><summary>Dossier Raw</summary><pre>${esc(JSON.stringify(d, null, 2))}</pre></details>
        </div>
      `;
    }

    function leadFor(id) { return state.leads.find(l => l.id === id); }
    function scoreFor(id) { return state.scores.find(s => s.lead_id === id); }

    function setFilter(filter) {
      activeFilter = filter;
      const visible = filteredDossiers();
      selectedId = visible.length ? visible[0].id : null;
      renderFilters();
      renderLeads();
      renderDrawer();
    }

    function selectCampaign(id) {
      selectedCampaignId = id;
      activeFilter = 'all';
      selectedId = null;
      render();
    }

    function selectLead(id) {
      selectedId = id;
      renderLeads();
      renderDrawer();
    }

    async function updateStage(event, id) {
      event.preventDefault();
      const stage = event.target.stage.value;
      await fetch(`/api/follow-up?id=${id}&stage=${stage}`, { method: 'POST' });
      load();
    }

    async function planCampaign() {
      const prompt = document.querySelector('textarea[name="prompt"]').value;
      document.querySelector('#run-status').textContent = 'Planning without external API calls...';
      const response = await fetch('/api/campaign-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      const result = await response.json();
      document.querySelector('#run-status').textContent =
        `Plan: ${(result.campaign.countries || []).join(', ')} / ${(result.campaign.industries || []).join(', ')} / ${result.active_search_providers.join(' + ')}`;
    }

    async function runCampaign(event) {
      event.preventDefault();
      const prompt = event.target.prompt.value;
      document.querySelector('#run-status').textContent = 'Running capped provider workflow...';
      const response = await fetch('/api/campaign-run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      const result = await response.json();
      selectedCampaignId = result.campaign.id;
      selectedId = null;
      document.querySelector('#run-status').textContent =
        `Created ${result.dossiers.length} dossiers, ${result.questions.length} open questions`;
      await load();
    }
    load();
  </script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    settings = load_settings()
    store = JsonStore(settings.data_dir)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            search_provider = build_search_provider(self.settings)
            crawl_provider = build_crawl_provider(self.settings)
            self._json(
                {
                    "campaigns": self.store.read_collection("campaigns"),
                    "leads": self.store.read_collection("leads"),
                    "scores": self.store.read_collection("scores"),
                    "dossiers": self.store.read_collection("dossiers"),
                    "buyer_signals": self.store.read_collection("buyer_signals"),
                    "solution_assessments": self.store.read_collection("solution_assessments"),
                    "source_plans": self.store.read_collection("source_plans"),
                    "clarifications": self.store.read_collection("clarifications"),
                    "provider_errors": self.store.read_collection("provider_errors"),
                    "settings": {
                        "active_search_providers": [
                            type(provider).__name__
                            for provider in getattr(search_provider, "providers", [search_provider])
                        ],
                        "active_crawl_provider": type(crawl_provider).__name__,
                        "max_candidates_per_run": self.settings.max_candidates_per_run,
                        "max_deep_analysis_per_run": self.settings.max_deep_analysis_per_run,
                    },
                }
            )
            return
        self._html(HTML)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/campaign-plan":
            payload = self._read_json()
            prompt = str(payload.get("prompt") or "").strip()
            if not prompt:
                self._json({"error": "prompt is required"}, status=400)
                return
            campaign = IcpPlannerAgent().plan(prompt)
            search_provider = build_search_provider(self.settings)
            crawl_provider = build_crawl_provider(self.settings)
            self._json(
                {
                    "campaign": to_jsonable(campaign),
                    "active_search_providers": [
                        type(provider).__name__
                        for provider in getattr(search_provider, "providers", [search_provider])
                    ],
                    "active_crawl_provider": type(crawl_provider).__name__,
                    "caps": {
                        "max_candidates_per_run": self.settings.max_candidates_per_run,
                        "max_deep_analysis_per_run": self.settings.max_deep_analysis_per_run,
                    },
                }
            )
            return
        if parsed.path == "/api/campaign-run":
            payload = self._read_json()
            prompt = str(payload.get("prompt") or "").strip()
            if not prompt:
                self._json({"error": "prompt is required"}, status=400)
                return
            campaign = IcpPlannerAgent().plan(prompt)

            def record_provider_error(error) -> None:
                self.store.upsert("provider_errors", to_jsonable(error))

            result = LeadGenerationOrchestrator(
                search_provider=build_search_provider(
                    self.settings, error_sink=record_provider_error
                ),
                crawl_provider=build_crawl_provider(self.settings),
                store=self.store,
                max_candidates_per_run=self.settings.max_candidates_per_run,
                max_deep_analysis_per_run=self.settings.max_deep_analysis_per_run,
            ).run_campaign(campaign)
            self._json(
                {
                    "campaign": to_jsonable(result.campaign),
                    "dossiers": to_jsonable(result.dossiers),
                    "questions": to_jsonable(result.questions),
                }
            )
            return
        if parsed.path == "/api/follow-up":
            params = parse_qs(parsed.query)
            dossier_id = params.get("id", [""])[0]
            stage = params.get("stage", ["new"])[0]
            rows = self.store.read_collection("dossiers")
            for row in rows:
                if row.get("id") == dossier_id:
                    row["follow_up_stage"] = stage
                    row["updated_at"] = utc_now()
            self.store.write_collection("dossiers", rows)
            self._json({"ok": True})
            return
        self.send_response(404)
        self.end_headers()

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode() or "{}")

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, body: str) -> None:
        encoded = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    Path(load_settings().data_dir).mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 8088), DashboardHandler)
    print("Dashboard running at http://127.0.0.1:8088")
    server.serve_forever()


if __name__ == "__main__":
    main()

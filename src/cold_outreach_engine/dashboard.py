from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cold_outreach_engine.agents.campaign_strategy import CampaignStrategyAgent
from cold_outreach_engine.config import load_settings
from cold_outreach_engine.models import to_jsonable, utc_now
from cold_outreach_engine.orchestrator import LeadGenerationOrchestrator
from cold_outreach_engine.providers.factory import (
    build_crawl_provider,
    build_llm_provider,
    build_search_provider,
)
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
      overflow: auto;
    }

    .shell { min-width: 1380px; height: 100vh; display: grid; grid-template-rows: 74px 1fr; }
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
      grid-template-columns: minmax(760px, 1fr) 300px 430px;
      height: calc(100vh - 74px);
      border-left: 1px solid var(--line);
    }
    aside, main, .drawer { min-height: 0; overflow: auto; }
    aside, .drawer { background: rgba(9, 10, 11, .58); }
    aside { grid-column: 2; border-left: 1px solid var(--line); border-right: 1px solid var(--line); }
    main { border-right: 1px solid var(--line); }
    .flow-main { grid-column: 1; grid-row: 1; }
    .drawer { grid-column: 3; grid-row: 1; }
    .panel { border-bottom: 1px solid var(--line); padding: 18px; }
    .panel.tight { padding: 14px 18px; }
    .flow-main { background: rgba(7, 8, 9, .28); }
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
    .command-textarea {
      min-height: 132px;
      font-size: 15px;
      line-height: 1.55;
      background: rgba(0,0,0,.18);
      border-color: rgba(255,255,255,.12);
      border-radius: 12px;
      font-family: var(--sans);
    }
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

    .stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
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

    .command-stage {
      padding: 34px 42px 28px;
      border-bottom: 1px solid var(--line);
      background:
        linear-gradient(180deg, rgba(255,255,255,.055), transparent 72%),
        rgba(255,255,255,.018);
    }
    .command-stage h1 {
      max-width: 880px;
      font-size: clamp(36px, 4vw, 58px);
    }
    .command-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 14px;
      margin-top: 22px;
      max-width: 980px;
      align-items: stretch;
    }
    .command-card {
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(255,255,255,.025);
      padding: 16px;
      min-width: 0;
    }
    .composer-card {
      background: rgba(17, 19, 21, .82);
      border-color: rgba(255,255,255,.2);
      box-shadow: 0 20px 60px rgba(0,0,0,.22), inset 0 1px 0 rgba(255,255,255,.04);
    }
    .response-card {
      background: rgba(255,255,255,.018);
      border-color: rgba(255,255,255,.1);
    }
    .prompt-readout {
      min-height: 68px;
      border: 1px solid rgba(255,255,255,.18);
      border-radius: 12px;
      padding: 13px;
      background: rgba(0,0,0,.22);
      font: 14px/1.55 var(--sans);
      color: #eef1ee;
      white-space: pre-wrap;
    }
    .chip-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }
    .chip {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 9px;
      font: 10px var(--mono);
      text-transform: uppercase;
      letter-spacing: .12em;
      color: #d7dad7;
      background: rgba(255,255,255,.026);
    }
    .agent-board {
      padding: 24px 42px;
      border-bottom: 1px solid var(--line);
    }
    .agent-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(300px, 1fr));
      gap: 12px;
      margin-top: 12px;
      max-width: 1180px;
    }
    .agent-card {
      position: relative;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,255,255,.024);
      padding: 14px;
      overflow: hidden;
    }
    .agent-card::before {
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: 3px;
      background: var(--dim);
    }
    .agent-card.ready::before { background: var(--good); }
    .agent-card.waiting::before { background: var(--warn); }
    .agent-card.pending {
      grid-column: 1 / -1;
      min-height: 0;
      background: rgba(255,255,255,.016);
    }
    .agent-card.pending::before { background: var(--dim); }
    .agent-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 12px;
    }
    .agent-index {
      width: 28px;
      height: 28px;
      border: 1px solid var(--line);
      border-radius: 50%;
      display: grid;
      place-items: center;
      font: 11px var(--mono);
      color: var(--muted);
      flex: 0 0 auto;
    }
    .agent-card h3 { font-size: 15px; }
    .agent-list {
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .agent-list li {
      border-top: 1px solid rgba(255,255,255,.08);
      padding-top: 8px;
      font: 11px/1.42 var(--mono);
      color: #cfd4cf;
    }
    .pending-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }
    .lead-section {
      padding: 24px 42px 34px;
    }
    .lead-section .lead-table {
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: rgba(255,255,255,.018);
      margin-top: 12px;
    }

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

    .filters { margin-top: 14px; }
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

      <main class="flow-main">
        <section class="command-stage">
          <div class="micro">Tyvexa / Prompt Operating Room</div>
          <h1>Prompt To Agent Workbench</h1>
          <div class="command-grid">
            <div class="command-card composer-card">
              <div class="panel-title">
                <h2>Ask The Engine</h2>
                <span class="micro">Prompt In</span>
              </div>
              <form onsubmit="runCampaign(event)">
                <textarea class="command-textarea" name="prompt" placeholder="Find me leads in [market] for [business type] looking for [capability]...">Find me leads in Finland for service businesses looking for voice AI capabilities</textarea>
                <div class="actions">
                  <button type="button" onclick="planCampaign()">Plan Only</button>
                  <button class="primary">Run Capped</button>
                </div>
                <div id="run-status" class="micro run-status"></div>
              </form>
            </div>
            <div class="command-card response-card">
              <div class="panel-title">
                <h2>Engine Interpretation</h2>
                <span class="micro" id="selected-campaign-label">No Run</span>
              </div>
              <div id="prompt-readout" class="prompt-readout">No campaign selected yet.</div>
              <div id="prompt-chips" class="chip-row"></div>
            </div>
          </div>
        </section>

        <section class="agent-board">
          <div class="panel-title">
            <h2>Agent Contributions</h2>
            <span class="micro" id="agent-count">00</span>
          </div>
          <div id="agent-trace" class="agent-grid"></div>
        </section>

        <section class="lead-section">
          <div class="panel-title">
            <h2>Lead Dossiers</h2>
            <span class="micro" id="lead-count">00</span>
          </div>
          <div class="stat-grid" id="stats"></div>
          <div class="filters" id="filters"></div>
          <section class="lead-table" id="lead-table"></section>
        </section>
      </main>

      <aside class="drawer" id="drawer"></aside>
    </div>
  </div>

  <script>
    const stages = ['new','linkedin_searched','contacted','follow_up_due','replied','not_fit','won','lost'];
    const filters = ['all','qualified','manual_review','needs_input','rejected'];
    let state = { campaigns: [], campaign_specs: [], dossiers: [], clarifications: [], provider_errors: [], leads: [], scores: [], buyer_signals: [], solution_assessments: [], source_plans: [], evidence_packs: [], lead_assessments: [], market_contexts: [], settings: {} };
    let activeFilter = 'all';
    let selectedCampaignId = null;
    let selectedId = null;
    let previewPlan = null;

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
      syncPromptInputFromSelection();
      render();
    }

    function render() {
      renderCampaigns();
      renderQuestions();
      renderPromptSummary();
      renderAgentTrace();
      renderStats();
      renderFilters();
      renderLeads();
      renderDrawer();
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
      document.querySelector('#stats').innerHTML = [
        ['Qualified', qualified],
        ['Review', review],
        ['Rejected', rejected],
      ].map(([label, value]) => `<div class="stat"><b>${fmt(value)}</b><span class="micro">${label}</span></div>`).join('');
    }

    function renderPromptSummary() {
      const campaign = currentCampaign();
      const spec = currentSpec();
      document.querySelector('#selected-campaign-label').textContent = campaign ? short(campaign.id, 18) : 'No Run';
      document.querySelector('#prompt-readout').textContent = campaign ? campaign.prompt : 'No campaign selected yet.';
      const chips = [];
      if (campaign) {
        chips.push(`Offer: ${campaign.offer || 'unknown'}`);
        chips.push(`Markets: ${(campaign.countries || []).join(', ') || 'unknown'}`);
        chips.push(`Targets: ${(campaign.industries || []).join(', ') || 'unknown'}`);
      }
      if (spec) {
        const strategy = spec.strategy_source === 'ai_api'
          ? `AI API${spec.strategy_model ? ' / ' + spec.strategy_model : ''}`
          : 'Fallback validator';
        chips.push(`Strategy: ${strategy}`);
        chips.push(`Spec: ${spec.version || 'dynamic'}`);
        chips.push(`Sources: ${(spec.source_priorities || []).slice(0, 3).join(' + ') || 'pending'}`);
      }
      document.querySelector('#prompt-chips').innerHTML = chips.map(chip => `<span class="chip">${esc(chip)}</span>`).join('');
    }

    function renderAgentTrace() {
      const campaign = currentCampaign();
      const spec = currentSpec();
      const sourcePlan = currentSourcePlan();
      const dossiers = currentCampaignDossiers();
      const leads = currentCampaignLeads();
      const evidencePacks = currentEvidencePacks();
      const assessments = currentAssessments();
      const markets = currentMarketContexts();
      const questions = currentQuestions();
      const signals = currentBuyerSignals();
      const solutionCount = currentSolutions().length;
      const statusCounts = assessments.reduce((acc, a) => { acc[a.status] = (acc[a.status] || 0) + 1; return acc; }, {});
      const sourceItems = sourcePlan ? [
        `${(sourcePlan.sources || []).length} source groups selected`,
        `${(sourcePlan.search_queries || []).length} generated search queries`,
        short((sourcePlan.search_queries || [])[0] || 'No query generated yet', 92),
      ] : ['Waiting for Campaign Strategy output.'];
      const agentDefinitions = [
        {
          index: 1,
          title: 'Campaign Strategy Agent',
          ready: !!campaign,
          items: [
          campaign ? `Offer: ${campaign.offer}` : 'Waiting for a prompt.',
          campaign ? `Targets: ${(campaign.industries || []).join(', ') || 'unknown'}` : 'No target segment yet.',
          spec ? `Strategy source: ${spec.strategy_source === 'ai_api' ? 'AI API' : 'fallback validator'}` : 'Strategy source pending.',
          spec ? `Pain hypotheses: ${(spec.pain_hypotheses || []).slice(0, 3).join('; ')}` : 'Dynamic spec not generated for this stored run.',
          ],
        },
        {
          index: 2,
          title: 'Discovery Agent',
          ready: !!sourcePlan || leads.length > 0,
          items: [
          ...sourceItems,
          `${leads.length} candidate leads currently attached to this campaign`,
          ],
        },
        {
          index: 3,
          title: 'Evidence Agent',
          ready: evidencePacks.length > 0,
          items: [
          `${evidencePacks.length} evidence packs built`,
          markerSummary(evidencePacks, 'contact_markers', 'contact markers'),
          markerSummary(evidencePacks, 'pain_markers', 'pain markers'),
          ],
        },
        {
          index: 4,
          title: 'Qualification Agent',
          ready: assessments.length > 0 || signals.length > 0 || solutionCount > 0,
          items: [
          `${assessments.length} lead assessments`,
          `Statuses: ${Object.entries(statusCounts).map(([k, v]) => `${k} ${v}`).join(' / ') || 'pending'}`,
          `${signals.length} buyer signals and ${solutionCount} solution checks`,
          ],
        },
        {
          index: 5,
          title: 'Market Context Agent',
          ready: markets.length > 0,
          items: [
          `${markets.length} market contexts`,
          markerSummary(markets, 'gap_hypotheses', 'gap hypotheses'),
          short((markets[0] || {}).summary || 'Competitor context waits for enrichment.', 92),
          ],
        },
        {
          index: 6,
          title: 'Dossier Agent',
          ready: dossiers.length > 0,
          items: [
          `${dossiers.length} lead dossiers ready`,
          `${dossiers.filter(d => d.status === 'qualified').length} qualified for manual review/outreach`,
          short((dossiers[0] || {}).manual_opening_message || 'No outreach angle yet.', 92),
          ],
        },
        {
          index: 7,
          title: 'Clarification Layer',
          ready: questions.length > 0,
          items: [
          `${questions.length} open questions`,
          short((questions[0] || {}).question || 'No clarification needed for the selected run.', 92),
          'Activates when evidence or campaign scope is too thin.',
          ],
        },
      ];
      const readyCards = agentDefinitions
        .filter(agent => agent.ready)
        .map(agent => agentCard(agent.index, agent.title, agent.ready, agent.items));
      const pendingAgents = agentDefinitions.filter(agent => !agent.ready);
      if (pendingAgents.length) readyCards.push(pendingCard(pendingAgents));
      document.querySelector('#agent-count').textContent = fmt(agentDefinitions.length);
      document.querySelector('#agent-trace').innerHTML = readyCards.join('');
    }

    function agentCard(index, title, ready, items) {
      const status = ready ? 'ready' : 'waiting';
      return `
        <article class="agent-card ${status}">
          <div class="agent-head">
            <div>
              <div class="micro">${ready ? 'Output available' : 'Waiting'}</div>
              <h3>${esc(title)}</h3>
            </div>
            <div class="agent-index">${fmt(index)}</div>
          </div>
          <ul class="agent-list">${items.map(item => `<li>${esc(item)}</li>`).join('')}</ul>
        </article>
      `;
    }

    function pendingCard(agents) {
      return `
        <article class="agent-card pending">
          <div class="agent-head">
            <div>
              <div class="micro">Pending Until Run</div>
              <h3>Agents Waiting For Lead Evidence</h3>
            </div>
            <div class="agent-index">${fmt(agents.length)}</div>
          </div>
          <div class="pending-row">
            ${agents.map(agent => `<span class="chip">${esc(agent.title)}</span>`).join('')}
          </div>
        </article>
      `;
    }

    function markerSummary(rows, key, label) {
      const values = [];
      rows.forEach(row => (row[key] || []).forEach(value => {
        if (value && !values.includes(value)) values.push(value);
      }));
      return `${values.length} ${label}: ${values.slice(0, 4).join(', ') || 'pending'}`;
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

    function currentCampaign() {
      if (previewPlan && previewPlan.campaign && previewPlan.campaign.id === selectedCampaignId) {
        return previewPlan.campaign;
      }
      return state.campaigns.find(c => c.id === selectedCampaignId) || null;
    }

    function currentSpec() {
      if (previewPlan && previewPlan.campaign_spec && previewPlan.campaign?.id === selectedCampaignId) {
        return previewPlan.campaign_spec;
      }
      return state.campaign_specs.find(s => s.campaign_id === selectedCampaignId) || null;
    }

    function currentSourcePlan() {
      const spec = currentSpec();
      if (spec) {
        return {
          sources: spec.source_priorities || [],
          search_queries: spec.search_queries || [],
        };
      }
      return state.source_plans.find(p => p.campaign_id === selectedCampaignId) || null;
    }

    function currentCampaignLeads() {
      if (!selectedCampaignId) return state.leads;
      return state.leads.filter(l => l.campaign_id === selectedCampaignId);
    }

    function currentEvidencePacks() {
      const leadIds = new Set(currentCampaignLeads().map(l => l.id));
      return state.evidence_packs.filter(p => leadIds.has(p.lead_id));
    }

    function currentAssessments() {
      const leadIds = new Set(currentCampaignLeads().map(l => l.id));
      return state.lead_assessments.filter(a => leadIds.has(a.lead_id));
    }

    function currentMarketContexts() {
      const leadIds = new Set(currentCampaignLeads().map(l => l.id));
      return state.market_contexts.filter(m => leadIds.has(m.lead_id));
    }

    function currentBuyerSignals() {
      const leadIds = new Set(currentCampaignLeads().map(l => l.id));
      return state.buyer_signals.filter(s => leadIds.has(s.lead_id));
    }

    function currentSolutions() {
      const leadIds = new Set(currentCampaignLeads().map(l => l.id));
      return state.solution_assessments.filter(s => leadIds.has(s.lead_id));
    }

    function currentQuestions() {
      return state.clarifications.filter(q => !selectedCampaignId || q.campaign_id === selectedCampaignId);
    }

    function syncPromptInputFromSelection() {
      const input = document.querySelector('textarea[name="prompt"]');
      const campaign = currentCampaign();
      if (!input || !campaign || previewPlan || document.activeElement === input) return;
      input.value = campaign.prompt || input.value;
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
      const evidencePack = state.evidence_packs.find(p => p.lead_id === d.lead_id);
      const assessment = state.lead_assessments.find(a => a.lead_id === d.lead_id);
      const market = state.market_contexts.find(m => m.lead_id === d.lead_id);
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
          ${assessment ? `<details><summary>Lead Assessment</summary><pre>${esc(JSON.stringify(assessment, null, 2))}</pre></details>` : ''}
          ${evidencePack ? `<details><summary>Evidence Pack</summary><pre>${esc(JSON.stringify(evidencePack, null, 2))}</pre></details>` : ''}
          ${market ? `<details><summary>Market Context</summary><pre>${esc(JSON.stringify(market, null, 2))}</pre></details>` : ''}
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
      if (!previewPlan || previewPlan.campaign?.id !== id) previewPlan = null;
      activeFilter = 'all';
      selectedId = null;
      syncPromptInputFromSelection();
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
      document.querySelector('#run-status').textContent = 'Planning strategy spec; no discovery providers yet...';
      const response = await fetch('/api/campaign-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      const result = await response.json();
      previewPlan = result;
      selectedCampaignId = result.campaign.id;
      selectedId = null;
      document.querySelector('#run-status').textContent =
        `Spec: ${(result.campaign.countries || []).join(', ')} / ${(result.campaign.industries || []).join(', ')} / ${(result.campaign_spec.strategy_source || 'unknown strategy')} / ${(result.campaign_spec.source_priorities || result.active_search_providers).join(' + ')}`;
      render();
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
      previewPlan = null;
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
            llm_provider = build_llm_provider(self.settings)
            self._json(
                {
                    "campaigns": self.store.read_collection("campaigns"),
                    "campaign_specs": self.store.read_collection("campaign_specs"),
                    "leads": self.store.read_collection("leads"),
                    "scores": self.store.read_collection("scores"),
                    "dossiers": self.store.read_collection("dossiers"),
                    "evidence_packs": self.store.read_collection("evidence_packs"),
                    "lead_assessments": self.store.read_collection("lead_assessments"),
                    "market_contexts": self.store.read_collection("market_contexts"),
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
                        "active_strategy_provider": type(llm_provider).__name__
                        if llm_provider
                        else "heuristic_fallback",
                        "strategy_model": self.settings.openai_model
                        if llm_provider
                        else None,
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
            llm_provider = build_llm_provider(self.settings)
            campaign, spec = CampaignStrategyAgent(llm_provider).plan(prompt)
            search_provider = build_search_provider(self.settings)
            crawl_provider = build_crawl_provider(self.settings)
            self._json(
                {
                    "campaign": to_jsonable(campaign),
                    "campaign_spec": to_jsonable(spec),
                    "active_search_providers": [
                        type(provider).__name__
                        for provider in getattr(search_provider, "providers", [search_provider])
                    ],
                    "active_crawl_provider": type(crawl_provider).__name__,
                    "active_strategy_provider": type(llm_provider).__name__
                    if llm_provider
                    else "heuristic_fallback",
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
            llm_provider = build_llm_provider(self.settings)
            campaign, spec = CampaignStrategyAgent(llm_provider).plan(prompt)

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
                strategy_agent=CampaignStrategyAgent(llm_provider),
            ).run_campaign(campaign, spec)
            self._json(
                {
                    "campaign": to_jsonable(result.campaign),
                    "campaign_spec": to_jsonable(result.spec),
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

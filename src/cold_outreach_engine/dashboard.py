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
  <title>Cold Outreach Engine</title>
  <style>
    body { font-family: Inter, system-ui, sans-serif; margin: 0; background: #f7f7f4; color: #20201d; }
    header { padding: 20px 28px; background: #1f2933; color: white; }
    main { display: grid; grid-template-columns: 320px 1fr; gap: 18px; padding: 18px; }
    section { background: white; border: 1px solid #ddd8ce; border-radius: 8px; padding: 16px; }
    h1 { font-size: 22px; margin: 0; }
    h2 { font-size: 16px; margin: 0 0 12px; }
    .lead { border: 1px solid #e1ddd4; border-radius: 8px; padding: 12px; margin-bottom: 10px; }
    .meta { color: #68645d; font-size: 13px; }
    .status { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #e9f1ff; font-size: 12px; }
    button, select { border: 1px solid #bbb4a8; background: #fff; border-radius: 6px; padding: 7px 9px; }
    textarea { width: 100%; min-height: 78px; }
    pre { white-space: pre-wrap; background: #f3f1ed; padding: 10px; border-radius: 6px; }
  </style>
</head>
<body>
  <header>
    <h1>Cold Outreach Engine</h1>
    <div class="meta">Dynamic lead generation, manual outreach, follow-up tracking</div>
  </header>
  <main>
    <section>
      <h2>New Lead Run</h2>
      <form class="lead" onsubmit="runCampaign(event)">
        <textarea name="prompt">Find me leads in Finland for restaurant businesses looking for voice AI capabilities</textarea>
        <button>Run Lead Gen</button>
        <div id="run-status" class="meta"></div>
      </form>
      <h2>Campaigns</h2>
      <div id="campaigns"></div>
      <h2>Open Questions</h2>
      <div id="questions"></div>
    </section>
    <section>
      <h2>Lead Dossiers</h2>
      <div id="dossiers"></div>
    </section>
  </main>
  <script>
    async function load() {
      const data = await fetch('/api/state').then(r => r.json());
      document.querySelector('#campaigns').innerHTML = data.campaigns.map(c =>
        `<div class="lead"><b>${c.offer}</b><div class="meta">${c.countries.join(', ')} | ${c.industries.join(', ')}</div></div>`
      ).join('') || '<div class="meta">No campaigns yet. Run the sample CLI first.</div>';

      document.querySelector('#questions').innerHTML = data.clarifications.map(q =>
        `<div class="lead"><span class="status">${q.scope}</span><p>${q.question}</p><div class="meta">${q.status}</div></div>`
      ).join('') || '<div class="meta">No clarification questions.</div>';

      document.querySelector('#dossiers').innerHTML = data.dossiers.map(d =>
        `<div class="lead">
          <span class="status">${d.status}</span>
          <h3>${d.company_name}</h3>
          <div class="meta">Score ${d.score} | Follow-up: ${d.follow_up_stage}</div>
          <p>${d.why_this_lead}</p>
          <pre>${d.manual_opening_message}</pre>
          <form onsubmit="updateStage(event, '${d.id}')">
            <select name="stage">
              ${['new','linkedin_searched','contacted','follow_up_due','replied','not_fit','won','lost'].map(s => `<option ${s===d.follow_up_stage?'selected':''}>${s}</option>`).join('')}
            </select>
            <button>Update</button>
          </form>
        </div>`
      ).join('') || '<div class="meta">No dossiers yet.</div>';
    }

    async function updateStage(event, id) {
      event.preventDefault();
      const stage = event.target.stage.value;
      await fetch(`/api/follow-up?id=${id}&stage=${stage}`, { method: 'POST' });
      load();
    }

    async function runCampaign(event) {
      event.preventDefault();
      const prompt = event.target.prompt.value;
      document.querySelector('#run-status').textContent = 'Running...';
      const response = await fetch('/api/campaign-run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      const result = await response.json();
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
            self._json(
                {
                    "campaigns": self.store.read_collection("campaigns"),
                    "dossiers": self.store.read_collection("dossiers"),
                    "clarifications": self.store.read_collection("clarifications"),
                }
            )
            return
        self._html(HTML)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/campaign-run":
            payload = self._read_json()
            prompt = str(payload.get("prompt") or "").strip()
            if not prompt:
                self._json({"error": "prompt is required"}, status=400)
                return
            campaign = IcpPlannerAgent().plan(prompt)
            result = LeadGenerationOrchestrator(
                search_provider=build_search_provider(self.settings),
                crawl_provider=build_crawl_provider(self.settings),
                store=self.store,
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

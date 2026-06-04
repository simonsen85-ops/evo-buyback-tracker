#!/usr/bin/env python3
"""Generates index.html from data.json for the Evolution AB buyback tracker."""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "data.json"
OUTPUT_FILE = ROOT / "index.html"


def build():
    with open(DATA_FILE) as f:
        data = json.load(f)
    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    html = HTML_TEMPLATE.replace("__DATA_JSON__", data_json)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Built {OUTPUT_FILE} with {len(data['announcements'])} announcements")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EVO.ST — Tilbagekøbs-Tracker</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Outfit:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
/*
  TYPE HIERARCHY — 4 levels (T1 primary → T4 structural)
  GREEN SPECTRUM — G1 subtle → G4 deepest
  Pattern matches FED & IMB trackers
*/
:root{
  --bg:#0c1017;--bg2:#141a24;--bg3:#1a2230;
  --t1:#f8fafc;--t2:#b0bac9;--t3:#6b7a90;--t4:#3d4a5c;
  --g1:#6ee7b7;--g2:#34d399;--g3:#10b981;--g4:#059669;
  --amb:#f59e0b;--red:#ef4444;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'JetBrains Mono',monospace;background:var(--bg);color:var(--t1);min-height:100vh;font-size:13px;-webkit-font-smoothing:antialiased}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse at 70% 10%,rgba(16,185,129,.025),transparent 60%);pointer-events:none}
.c{max-width:1360px;margin:0 auto;padding:16px 20px;position:relative;z-index:1}

/* HEADER */
.hdr{display:flex;align-items:center;justify-content:space-between;padding:10px 0;margin-bottom:16px;border-bottom:1px solid var(--t4);flex-wrap:wrap;gap:12px}
.hdr-l{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.hdr-l h1{font-family:'Outfit',sans-serif;font-size:1.1rem;font-weight:600;color:var(--t1)}
.hdr-l .tk{color:var(--g3);font-weight:600;font-size:.85rem}
.hdr-l .tg{color:var(--t3);font-size:.75rem}
.hdr-l .badge{background:rgba(110,231,183,.15);color:var(--g1);border:1px solid rgba(110,231,183,.3);padding:2px 8px;border-radius:3px;font-size:.65rem;font-weight:600;letter-spacing:.5px;text-transform:uppercase}
.hdr-r{display:flex;gap:20px;align-items:center;font-size:.8rem}
.hdr-r .pair .lb{color:var(--t2);font-size:.65rem;text-transform:uppercase;letter-spacing:.5px}
.hdr-r .pair .vl{color:var(--t1);font-weight:600}
.hdr-r .pair .vl.g{color:var(--g2)}
.hdr-r .pair .vl.r{color:var(--red)}

/* PROGRAMME STATUS BAR */
.psb{background:var(--bg2);border:1px solid var(--t4);border-radius:4px;padding:14px 16px;margin-bottom:16px}
.psb-h{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px}
.psb-l{font-family:'Outfit',sans-serif;font-size:.75rem;font-weight:600;color:var(--t1);text-transform:uppercase;letter-spacing:.6px}
.psb-s{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:99px;font-size:.65rem;font-weight:600;text-transform:uppercase;letter-spacing:.7px}
.psb-s.active{background:rgba(52,211,153,.15);color:var(--g2);border:1px solid rgba(52,211,153,.3)}
.psb-s.done{background:rgba(107,122,144,.15);color:var(--t3);border:1px solid rgba(107,122,144,.3)}
.psb-dot{width:5px;height:5px;border-radius:50%;background:var(--g2);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.psb-bar{height:6px;background:var(--bg3);border-radius:3px;overflow:hidden;margin-bottom:6px}
.psb-bar-fill{height:100%;background:linear-gradient(90deg,var(--g4),var(--g2),var(--g1));transition:width 1s ease}
.psb-lbl{display:flex;justify-content:space-between;font-size:.7rem}
.psb-lbl .s{color:var(--g2);font-weight:600}
.psb-lbl .t{color:var(--t3)}

/* KPIs */
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:var(--t4);border:1px solid var(--t4);border-radius:4px;overflow:hidden;margin-bottom:16px}
@media(max-width:900px){.kpis{grid-template-columns:repeat(3,1fr)}}
@media(max-width:500px){.kpis{grid-template-columns:repeat(2,1fr)}}
.kpi{background:var(--bg2);padding:12px 14px}
.kpi .l{font-size:.65rem;color:var(--t2);text-transform:uppercase;letter-spacing:.7px;font-weight:500;margin-bottom:6px}
.kpi .v{font-size:1.2rem;font-weight:700;line-height:1}
.kpi .v.g{color:var(--g2)}
.kpi .v.a{color:var(--amb)}
.kpi .v.r{color:var(--red)}
.kpi .s{font-size:.7rem;color:var(--t2);margin-top:4px}

/* SECTION TITLE */
.sh{font-family:'Outfit',sans-serif;font-size:.75rem;font-weight:600;color:var(--t1);text-transform:uppercase;letter-spacing:.6px;margin-bottom:12px;margin-top:24px}

/* VALUE CREATION CARDS */
.vcg{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin-bottom:16px}
.vc{background:var(--bg2);border:1px solid var(--t4);border-radius:4px;padding:16px}
.vc-t{font-family:'Outfit',sans-serif;font-size:.78rem;font-weight:600;color:var(--t1);margin-bottom:12px}
.vc-r{display:flex;justify-content:space-between;align-items:baseline;padding:6px 0;border-bottom:1px solid var(--t4)}
.vc-r:last-child{border-bottom:none}
.vc-r .l{font-size:.72rem;color:var(--t2)}
.vc-r .v{font-size:.78rem;font-weight:600;color:var(--t1)}
.vc-r .v.g{color:var(--g2)}
.vc-r .v.r{color:var(--red)}
.vc-r .v.b{color:#60a5fa}

/* TABLES */
.tw{background:var(--bg2);border:1px solid var(--t4);border-radius:4px;overflow:hidden;margin-bottom:16px}
.ts{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.72rem}
thead{background:var(--bg3)}
th{padding:9px 12px;text-align:left;font-family:'Outfit',sans-serif;font-size:.62rem;font-weight:600;color:var(--t2);text-transform:uppercase;letter-spacing:.7px;white-space:nowrap;border-bottom:1px solid var(--t4)}
th.r,td.r{text-align:right}
td{padding:8px 12px;border-bottom:1px solid var(--t4);white-space:nowrap;color:var(--t1)}
tr:hover td{background:var(--bg3)}
tr:last-child td{border-bottom:none}
.empty{padding:24px;text-align:center;color:var(--t3);font-size:.72rem}
.totr td{font-weight:700;background:var(--bg3);border-top:2px solid var(--t4)}

/* FOOTER */
.notes{background:var(--bg2);border:1px solid var(--t4);border-radius:4px;padding:14px 16px;margin-top:16px;font-size:.7rem;color:var(--t3);line-height:1.7}
.notes a{color:#60a5fa;text-decoration:none}
.notes a:hover{text-decoration:underline}
.ftr{text-align:center;color:var(--t4);font-size:.65rem;margin-top:16px;letter-spacing:.7px}
</style>
</head>
<body>
<div class="c">

  <!-- HEADER -->
  <div class="hdr">
    <div class="hdr-l">
      <span class="tk" id="hdr-ticker">EVO</span>
      <h1 id="hdr-company">Evolution AB (publ)</h1>
      <span class="tg" id="hdr-exchange">Nasdaq Stockholm</span>
      <span class="badge" id="hdr-badge">€2 mia.</span>
    </div>
    <div class="hdr-r">
      <div class="pair">
        <div class="lb">Aktuel kurs</div>
        <div class="vl" id="hdr-price">—</div>
      </div>
      <div class="pair">
        <div class="lb">Total aktier</div>
        <div class="vl" id="hdr-shares">—</div>
      </div>
    </div>
  </div>

  <!-- PROGRAMME STATUS BAR -->
  <div class="psb">
    <div class="psb-h">
      <span class="psb-l" id="prog-label">—</span>
      <span class="psb-s" id="prog-status"><span class="psb-dot"></span>—</span>
    </div>
    <div class="psb-bar"><div class="psb-bar-fill" id="prog-bar" style="width:0%"></div></div>
    <div class="psb-lbl">
      <span class="s" id="prog-spent">—</span>
      <span class="t" id="prog-total">—</span>
    </div>
  </div>

  <!-- KPIs -->
  <div class="kpis" id="kpis"></div>

  <!-- VALUE CREATION -->
  <h2 class="sh">Værdiskabelse — Net Buyback Model</h2>
  <div class="vcg">
    <div class="vc">
      <div class="vc-t">FCF Yield & Kapacitet</div>
      <div class="vc-r"><span class="l">EBITDA 2025</span><span class="v">€1.457M</span></div>
      <div class="vc-r"><span class="l">EBITDA-margin</span><span class="v">~66%</span></div>
      <div class="vc-r"><span class="l">Est. FCF 2026E</span><span class="v g">~€1.050–1.150M</span></div>
      <div class="vc-r"><span class="l">FCF Yield (markedsv.)</span><span class="v g" id="vc-fcfy">—</span></div>
      <div class="vc-r"><span class="l">€2B vs. årligt FCF</span><span class="v b">~2x</span></div>
      <div class="vc-r"><span class="l">RCF som buffer</span><span class="v">€300M</span></div>
    </div>
    <div class="vc">
      <div class="vc-t">EPS-Accretion (Annullering)</div>
      <div class="vc-r"><span class="l">EPS 2025 (rapporteret)</span><span class="v">€5,23</span></div>
      <div class="vc-r"><span class="l">Udst. aktier</span><span class="v" id="vc-shares">—</span></div>
      <div class="vc-r"><span class="l">10%-cap</span><span class="v" id="vc-cap">—</span></div>
      <div class="vc-r"><span class="l">EPS-løft v. fuld cap</span><span class="v g">+11,1%</span></div>
      <div class="vc-r"><span class="l">SBC-udvanding (est.)</span><span class="v r">~0,3–0,5%</span></div>
      <div class="vc-r"><span class="l">Netto EPS-løft (10%)</span><span class="v g">+10,6–10,8%</span></div>
    </div>
    <div class="vc">
      <div class="vc-t">Programstørrelse i Kontekst</div>
      <div class="vc-r"><span class="l">€2B vs. €500M forrige</span><span class="v b">4x større</span></div>
      <div class="vc-r"><span class="l">Annulleret cap</span><span class="v g">19,92M aktier</span></div>
      <div class="vc-r"><span class="l">Følgeprogram muligt</span><span class="v">Ja (board)</span></div>
      <div class="vc-r"><span class="l">Reduktion 2023–25</span><span class="v g">~15%</span></div>
      <div class="vc-r"><span class="l">Pot. red. v. fuld €2B</span><span class="v g">~17%</span></div>
      <div class="vc-r"><span class="l">Implicit signal</span><span class="v g">Aggressiv tilbageførsel</span></div>
    </div>
  </div>

  <!-- PROGRAMME HISTORY -->
  <h2 class="sh">Tilbagekøbsprogrammer</h2>
  <div class="tw"><div class="ts">
    <table>
      <thead><tr><th>Program</th><th>Annonceret</th><th>Afsluttet</th><th class="r">Maks. beløb</th><th class="r">Aktier købt</th><th class="r">Status</th></tr></thead>
      <tbody id="prog-tbody"></tbody>
    </table>
  </div></div>

  <!-- ACTIVE TRANCHES -->
  <h2 class="sh">Ugentlige Tilbagekøb — Aktivt Program</h2>
  <div class="tw"><div class="ts">
    <table>
      <thead><tr><th>Periode</th><th class="r">Aktier</th><th class="r">Gns. kurs (SEK)</th><th class="r">Beløb (SEK)</th><th class="r">Kumulativt</th><th class="r">Treasury</th><th class="r">% af volumen</th></tr></thead>
      <tbody id="active-tbody"></tbody>
    </table>
  </div></div>

  <!-- HISTORIC TRANCHES -->
  <h2 class="sh">Tidligere Trancher — Historisk Reference</h2>
  <div class="tw"><div class="ts">
    <table>
      <thead><tr><th>Program</th><th>Periode</th><th class="r">Aktier</th><th class="r">Gns. kurs (SEK)</th><th class="r">Beløb (SEK)</th></tr></thead>
      <tbody id="historic-tbody"></tbody>
    </table>
  </div></div>

  <!-- NOTES -->
  <div class="notes">
    <strong style="color:var(--g2)">Primær kilde:</strong> <a href="https://www.nasdaqomxnordic.com/news/corporate-actions/repurchase-of-own-shares" target="_blank">Nasdaq Stockholm OAM</a> (officielle børsdistribuerede meddelelser)<br>
    <strong>Fallback:</strong> <a href="https://www.evolution.com/investors/press-releases/" target="_blank">evolution.com/investors</a><br>
    Volume-data fra Nasdaq Nordic chart API (primær) + Yahoo Finance (fallback)<br>
    Værdiskabelse: FCF yield, EPS-accretion via annulleringseffekt, net buyback (BB − SBC)<br>
    Treasury shares fra €500M-program (5,24M) blev annulleret før nyt program — frisk start<br>
    First-principles kildevalg: Børsens API > Selskab > Cision/distributører
  </div>

  <div class="ftr" id="ftr">EVOLUTION AB BUYBACK TRACKER · Ikke investeringsrådgivning</div>

</div>

<script>
const D = __DATA_JSON__;

// ──────────────────────────────────────────────────────────────
// Number formatting
// ──────────────────────────────────────────────────────────────
function fmtInt(n) {
  return (n || 0).toLocaleString('da-DK');
}
function fmtMoney(n, currency = 'SEK') {
  if (!n) return '—';
  const v = n / 1e6;
  return `${currency} ${v.toLocaleString('da-DK', {maximumFractionDigits:1})}M`;
}
function fmtBn(n, currency = 'SEK') {
  if (!n) return '—';
  return `${currency} ${(n / 1e9).toLocaleString('da-DK', {maximumFractionDigits:1})} mia.`;
}
function fmt2(n) {
  return (n || 0).toLocaleString('da-DK', {minimumFractionDigits:2, maximumFractionDigits:2});
}

// ──────────────────────────────────────────────────────────────
// Header
// ──────────────────────────────────────────────────────────────
const price = D.current_price || 0;
const totalShares = D.total_shares || 0;
const mcapSek = price * totalShares;
const EUR_SEK = 11.40;  // Approx for FCF yield calc

document.getElementById('hdr-ticker').textContent = (D.ticker || 'EVO').split('.')[0];
document.getElementById('hdr-company').textContent = D.company || 'Evolution AB (publ)';
document.getElementById('hdr-exchange').textContent = D.exchange || 'Nasdaq Stockholm';
document.getElementById('hdr-price').textContent = price ? `SEK ${fmt2(price)}` : '—';
document.getElementById('hdr-shares').textContent = fmtInt(totalShares);

// ──────────────────────────────────────────────────────────────
// Active programme bar
// ──────────────────────────────────────────────────────────────
const programs = D.programs || [];
const activeProgram = programs.find(p => !p.closed_on) || programs[programs.length - 1];

if (activeProgram) {
  // Compute spent under this program
  const progAnns = (D.announcements || []).filter(a => a.program_id === activeProgram.id);
  const progSharesAcq = progAnns.reduce((s, a) => s + (a.week_shares || 0), 0);
  const progAmtSek = progAnns.reduce((s, a) => s + (a.week_amount || 0), 0);
  const progAmtEur = progAmtSek / EUR_SEK;
  const progPct = (progAmtEur / activeProgram.max_eur) * 100;

  document.getElementById('prog-label').textContent =
    `${activeProgram.name} · ${activeProgram.start}${activeProgram.closed_on ? ` – ${activeProgram.closed_on}` : ''}`;
  document.getElementById('prog-status').innerHTML = activeProgram.closed_on
    ? `Afsluttet`
    : `<span class="psb-dot"></span>Aktiv`;
  document.getElementById('prog-status').className = `psb-s ${activeProgram.closed_on ? 'done' : 'active'}`;

  document.getElementById('prog-bar').style.width = `${Math.min(progPct, 100)}%`;
  document.getElementById('prog-spent').textContent =
    `~€${(progAmtEur / 1e6).toFixed(0)}M brugt · ${progPct.toFixed(1)}% deployeret`;
  document.getElementById('prog-total').textContent =
    `af €${(activeProgram.max_eur / 1e6).toLocaleString('da-DK')}M`;
}

// ──────────────────────────────────────────────────────────────
// KPIs
// ──────────────────────────────────────────────────────────────
const activeAnns = (D.announcements || []).filter(a =>
  activeProgram && a.program_id === activeProgram.id
);
const activeShares = activeAnns.reduce((s, a) => s + (a.week_shares || 0), 0);
const activeAmt = activeAnns.reduce((s, a) => s + (a.week_amount || 0), 0);
const latestAnn = activeAnns[activeAnns.length - 1];
const treasury = latestAnn?.treasury_shares ?? 0;
const maxShares = latestAnn?.max_program_shares ?? (Math.floor(totalShares * 0.1));

const fcfYieldPct = mcapSek > 0 ? (1100e6 / (mcapSek / EUR_SEK)) * 100 : 0;
const progSize = activeProgram?.max_eur || 0;
const progSizePctMcap = mcapSek > 0 ? (progSize / (mcapSek / EUR_SEK)) * 100 : 0;

const kpis = [
  {l: "Aktivt program", v: activeProgram ? `€${(activeProgram.max_eur/1e6).toLocaleString('da-DK')}M` : '—', vc: 'g', s: activeProgram?.announced || ''},
  {l: "Aktier købt (aktivt)", v: fmtInt(activeShares), s: `af maks. ${fmtInt(maxShares)} (10% cap)`},
  {l: "Treasury shares", v: fmtInt(treasury), s: `${totalShares ? ((treasury/totalShares)*100).toFixed(2) : '0'}% af udestående`},
  {l: "Udestående aktier", v: `${(totalShares/1e6).toFixed(1)}M`, vc: 'g', s: '5,24M annulleret fra €500M'},
  {l: "Markedsværdi", v: fmtBn(mcapSek), s: price ? `Live kurs ${fmt2(price)}` : ''},
  {l: "€2B vs. markedsværdi", v: `${progSizePctMcap.toFixed(1)}%`, vc: 'g', s: 'Implicit buyback yield'},
];

document.getElementById('kpis').innerHTML = kpis.map(k =>
  `<div class="kpi"><div class="l">${k.l}</div><div class="v ${k.vc || ''}">${k.v}</div>${k.s ? `<div class="s">${k.s}</div>` : ''}</div>`
).join('');

// ──────────────────────────────────────────────────────────────
// Value creation panel updates
// ──────────────────────────────────────────────────────────────
document.getElementById('vc-fcfy').textContent = fcfYieldPct > 0 ? `~${fcfYieldPct.toFixed(1)}%` : '—';
document.getElementById('vc-shares').textContent = `${(totalShares/1e6).toFixed(1)}M`;
document.getElementById('vc-cap').textContent = fmtInt(maxShares);

// ──────────────────────────────────────────────────────────────
// Programme history table
// ──────────────────────────────────────────────────────────────
const progTbody = document.getElementById('prog-tbody');
programs.forEach(p => {
  const progAnns = (D.announcements || []).filter(a => a.program_id === p.id);
  const progShares = progAnns.reduce((s, a) => s + (a.week_shares || 0), 0);
  const isActive = !p.closed_on;
  const status = isActive
    ? '<span style="color:var(--g2);font-weight:700">AKTIV</span>'
    : '<span style="color:var(--g2)">Fuldført</span>';
  const row = `<tr${isActive ? ' class="totr"' : ''}>
    <td>${p.name}</td>
    <td>${p.announced || '—'}</td>
    <td>${p.closed_on || '—'}</td>
    <td class="r">€${(p.max_eur/1e6).toLocaleString('da-DK')}M</td>
    <td class="r">${progShares ? fmtInt(progShares) : '—'}</td>
    <td class="r">${status}</td>
  </tr>`;
  progTbody.insertAdjacentHTML('beforeend', row);
});

// ──────────────────────────────────────────────────────────────
// Active tranches table
// ──────────────────────────────────────────────────────────────
const activeTbody = document.getElementById('active-tbody');
if (activeAnns.length === 0) {
  activeTbody.innerHTML =
    `<tr><td colspan="7" class="empty">Programmet startede ${activeProgram?.start || '—'} — første ugentlige rapport ventes inden for få dage.<br>Data hentes automatisk fra Nasdaq Stockholm.</td></tr>`;
} else {
  // Newest first
  [...activeAnns].reverse().forEach(a => {
    const pctVol = a.buyback_pct_of_volume ?? 0;
    activeTbody.insertAdjacentHTML('beforeend', `<tr>
      <td>${a.period_start} – ${a.period_end}</td>
      <td class="r">${fmtInt(a.week_shares)}</td>
      <td class="r">${a.week_avg_price ? fmt2(a.week_avg_price) : '—'}</td>
      <td class="r">${a.week_amount ? fmtInt(a.week_amount) : '—'}</td>
      <td class="r">${fmtInt(a.acc_shares)}</td>
      <td class="r">${a.treasury_shares ? fmtInt(a.treasury_shares) : '—'}</td>
      <td class="r">${pctVol ? pctVol.toFixed(1) + '%' : '—'}</td>
    </tr>`);
  });
}

// ──────────────────────────────────────────────────────────────
// Historic tranches table
// ──────────────────────────────────────────────────────────────
const historicTbody = document.getElementById('historic-tbody');
const histAnns = (D.announcements || []).filter(a =>
  !activeProgram || a.program_id !== activeProgram.id
);
if (histAnns.length === 0) {
  historicTbody.innerHTML = '<tr><td colspan="5" class="empty">Ingen historiske trancher i data.json endnu.</td></tr>';
} else {
  const progMap = Object.fromEntries(programs.map(p => [p.id, p.name]));
  [...histAnns].reverse().forEach(a => {
    historicTbody.insertAdjacentHTML('beforeend', `<tr>
      <td>${progMap[a.program_id] || '—'}</td>
      <td>${a.period_start} – ${a.period_end}</td>
      <td class="r">${fmtInt(a.week_shares)}</td>
      <td class="r">${a.week_avg_price ? fmt2(a.week_avg_price) : '—'}</td>
      <td class="r">${a.week_amount ? fmtInt(a.week_amount) : '—'}</td>
    </tr>`);
  });
}

// Footer
document.getElementById('ftr').textContent =
  `EVOLUTION AB BUYBACK TRACKER · Sidst opdateret: ${D.last_updated ? D.last_updated.split('T')[0] : '—'} · Ikke investeringsrådgivning`;
</script>
</body>
</html>"""


if __name__ == "__main__":
    build()

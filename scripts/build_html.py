#!/usr/bin/env python3
"""Generates index.html from data.json for the Evolution AB buyback tracker.

Lean Bloomberg-style dashboard mirroring FED + IMB layout:
  Header -> 6 KPIs -> Value flow (A->B->C) -> Program progress -> 5 charts -> Sortable table
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "data.json"
OUTPUT_FILE = ROOT / "index.html"


def build():
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = HTML_TEMPLATE.replace("__DATA_JSON__", data_json)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Built {OUTPUT_FILE} with {len(data.get('announcements', []))} announcements")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EVO.ST — Tilbagekøbs-Tracker</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Outfit:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
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
.hdr{display:flex;align-items:center;justify-content:space-between;padding:10px 0;margin-bottom:16px;border-bottom:1px solid var(--t4);flex-wrap:wrap;gap:12px}
.hdr-l{display:flex;align-items:baseline;gap:12px}
.hdr-l h1{font-family:'Outfit',sans-serif;font-size:1.1rem;font-weight:600;color:var(--t1)}
.hdr-l .tk{color:var(--g3);font-weight:600;font-size:.85rem}
.hdr-l .tg{color:var(--t3);font-size:.75rem}
.hdr-r{display:flex;gap:20px;align-items:center;font-size:.8rem}
.hdr-r .pair .lb{color:var(--t2);font-size:.65rem;text-transform:uppercase;letter-spacing:.5px}
.hdr-r .pair .vl{color:var(--t1);font-weight:600}
.hdr-r .pair .vl.g{color:var(--g2)}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:var(--t4);border:1px solid var(--t4);border-radius:4px;overflow:hidden;margin-bottom:16px}
@media(max-width:900px){.kpis{grid-template-columns:repeat(3,1fr)}}
@media(max-width:500px){.kpis{grid-template-columns:repeat(2,1fr)}}
.kpi{background:var(--bg2);padding:12px 14px}
.kpi .l{font-size:.65rem;color:var(--t2);text-transform:uppercase;letter-spacing:.7px;font-weight:500;margin-bottom:6px}
.kpi .v{font-size:1.2rem;font-weight:700;line-height:1}
.kpi .s{font-size:.7rem;color:var(--t2);margin-top:4px}
.sh{font-family:'Outfit',sans-serif;font-size:.75rem;font-weight:600;color:var(--t1);text-transform:uppercase;letter-spacing:.6px;margin-bottom:12px}
.vc{background:var(--bg2);border:1px solid var(--t4);border-radius:4px;padding:14px 16px;margin-bottom:16px}
.vc-flow{display:grid;grid-template-columns:1fr 30px 1fr 30px 1fr;gap:8px;align-items:stretch}
@media(max-width:700px){.vc-flow{grid-template-columns:1fr}.vc-ar{transform:rotate(90deg)}}
.vb{border-radius:4px;padding:16px;text-align:center;display:flex;flex-direction:column;justify-content:center;align-items:center;width:100%}
.vb.a{background:rgba(248,250,252,.03);border:1px solid var(--t4)}
.vb.b{background:rgba(52,211,153,.04);border:1px solid rgba(52,211,153,.12)}
.vb.c{background:rgba(5,150,105,.07);border:1px solid rgba(5,150,105,.2)}
.vb .nm{font-size:1.3rem;font-weight:700}
.vb .lb{font-size:.63rem;color:var(--t2);margin-top:4px;text-transform:uppercase;letter-spacing:.5px}
.vb .dt{font-size:.7rem;color:var(--t2);margin-top:6px;line-height:1.5}
.vc-ar{font-size:1rem;color:var(--t3);display:flex;align-items:center;justify-content:center}
.vc-n{font-size:.67rem;color:var(--t3);margin-top:10px;line-height:1.5;padding-top:10px;border-top:1px solid var(--t4)}
.prog{background:var(--bg2);border:1px solid var(--t4);border-radius:4px;padding:14px 16px;margin-bottom:16px}
.prog-top{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}
.prog-top .pct{font-size:.85rem;font-weight:700;color:var(--g3)}
.prog-bar{height:6px;background:var(--bg3);border-radius:3px;overflow:hidden}
.prog-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--g4),var(--g3));transition:width 1s}
.prog-lbl{display:flex;justify-content:space-between;margin-top:5px;font-size:.65rem;color:var(--t2)}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px}
@media(max-width:860px){.charts{grid-template-columns:1fr}}
.chc{background:var(--bg2);border:1px solid var(--t4);border-radius:4px;padding:14px 16px}
.chc h3{font-family:'Outfit',sans-serif;font-size:.73rem;font-weight:600;margin-bottom:10px;color:var(--t1);text-transform:uppercase;letter-spacing:.5px}
.chc h3 span{font-weight:400;color:var(--t3)}
.chw{position:relative;height:260px}
.tc{background:var(--bg2);border:1px solid var(--t4);border-radius:4px;padding:14px 16px;margin-bottom:16px;overflow:hidden}
.ts{overflow-x:auto;max-width:100%}
table{width:100%;border-collapse:collapse}
th{text-align:right;padding:6px 8px;border-bottom:2px solid var(--t4);font-size:.63rem;text-transform:uppercase;letter-spacing:.5px;color:var(--t2);font-weight:600;white-space:nowrap;cursor:pointer;user-select:none;transition:color .15s}
th:hover{color:var(--t1)}
th .arrow{font-size:.55rem;margin-left:3px;opacity:.4}
th.active .arrow{opacity:1;color:var(--g3)}
th:first-child,th:nth-child(2){text-align:left}
td{padding:6px 8px;border-bottom:1px solid var(--t4);font-size:.72rem;text-align:right;color:var(--t1);white-space:nowrap}
td:first-child,td:nth-child(2){text-align:left}
td:first-child{color:var(--t3)}
tr:hover td{background:rgba(16,185,129,.02)}
.foot{display:flex;justify-content:center;gap:16px;padding:14px 0;font-size:.65rem;color:var(--t3)}
.foot a{color:var(--g3);text-decoration:none}
</style>
</head>
<body>
<div class="c">
<div class="hdr">
  <div class="hdr-l">
    <h1>Evolution AB (publ)</h1>
    <span class="tk">EVO.ST</span>
    <span class="tg">Safe Harbour Tilbagekøb</span>
  </div>
  <div class="hdr-r">
    <div class="pair"><div class="lb">Kurs</div><div class="vl" id="hKrs"></div></div>
    <div class="pair"><div class="lb">Mkt.værdi</div><div class="vl g" id="hMcap"></div></div>
    <div class="pair"><div class="lb">Treasury</div><div class="vl" id="hTr"></div></div>
  </div>
</div>
<div class="kpis" id="kpis"></div>
<div class="vc">
  <div class="sh">Værdiskabelse ved annullering</div>
  <div class="vc-flow" id="vcG"></div>
  <div class="vc-n" id="mn"></div>
</div>
<div class="prog">
  <div class="prog-top">
    <span class="sh" style="margin:0" id="pHdr">Programmer</span>
    <select id="pSel" style="background:var(--bg3);color:var(--t1);border:1px solid var(--t4);border-radius:3px;padding:4px 8px;font-family:'JetBrains Mono',monospace;font-size:.7rem;cursor:pointer;margin-left:auto;margin-right:12px">
      <option value="active">Aktivt program</option>
      <option value="all">Alle programmer (samlet)</option>
    </select>
    <span class="pct" id="pPct"></span>
  </div>
  <div class="prog-bar"><div class="prog-fill" id="pF"></div></div>
  <div class="prog-lbl"><span>0</span><span id="pL"></span><span id="pMax">—</span></div>
  <div id="pDetail" style="margin-top:8px;display:flex;gap:20px;flex-wrap:wrap;font-size:.65rem;color:var(--t2)"></div>
</div>
<div class="charts">
  <div class="chc"><h3>Kurs vs. tilbagekøbskurs <span>— SEK/aktie</span></h3><div class="chw"><canvas id="ch1"></canvas></div></div>
  <div class="chc"><h3>Treasury akkumulering <span>— % af udestående aktier</span></h3><div class="chw"><canvas id="ch2"></canvas></div></div>
  <div class="chc"><h3>Kumulativt forbrug <span>— SEK</span></h3><div class="chw"><canvas id="ch3"></canvas></div></div>
  <div class="chc"><h3>Handelsvolumen <span>— tilbagekøb vs. marked</span></h3><div class="chw"><canvas id="ch4"></canvas></div></div>
  <div class="chc" style="grid-column:1/-1"><h3>Safe Harbour-udnyttelse <span>— faktisk køb vs. dagligt 25%-loft af 20-dages gns. volumen</span></h3><div class="chw" style="height:200px"><canvas id="ch5"></canvas></div></div>
</div>
<div class="tc">
  <div class="sh">Ugentligt køb og likviditet</div>
  <div class="ts"><table id="tbl"><thead><tr></tr></thead><tbody id="tb"></tbody></table></div>
</div>
<div class="foot">
  <span>Kilde: <a href="https://www.evolution.com/investors/press-releases/" target="_blank">evolution.com/investors</a> (PDF'er fra Cision)</span>
  <span>·</span><span>Auto-opdateret hverdage 17:30 CET</span><span>·</span><span id="upd"></span>
</div>
</div>
<script>
const D = __DATA_JSON__;
const ANNS = (D.announcements||[]).slice().sort((a,b)=>(a.period_end||"").localeCompare(b.period_end||""));
const PROGS = D.programs || [];
const ACTIVE_PROG = PROGS.find(p=>!p.closed_on) || PROGS[PROGS.length-1];
const EUR_SEK = 11.40;
const EPS_2025 = 5.23;
function fD(n){return (n||0).toLocaleString('da-DK')}
function fM(n){return (n/1e6).toFixed(2)}
function fK(n){return (n/1e3).toFixed(0)}
function f2(n){return (n||0).toLocaleString('da-DK',{minimumFractionDigits:2,maximumFractionDigits:2})}
function fB(n){return (n/1e9).toLocaleString('da-DK',{maximumFractionDigits:2})}

function calc(){
  const rows=[]; let aS=0, aAmt=0;
  for (let i=0;i<ANNS.length;i++){
    const a=ANNS[i];
    aS += (a.week_shares||0); aAmt += (a.week_amount||0);
    const avgPrice = aS>0 ? aAmt/aS : 0;
    const treasury = a.treasury_shares != null ? a.treasury_shares : aS;
    const totalOut = a.total_shares_outstanding || D.total_shares;
    const maxProg = a.max_program_shares || Math.floor(totalOut*0.10);
    rows.push({
      i: i+1, d: a.period_end, ps: a.period_start,
      wS: a.week_shares||0, wA: a.week_avg_price||0, wAmt: a.week_amount||0,
      aS, aAmt, avg: avgPrice, treasury, totalOut, maxProg,
      capPct: maxProg>0 ? treasury/maxProg*100 : 0,
      sharePct: totalOut>0 ? treasury/totalOut*100 : 0,
      mVol: a.market_volume||0, bPct: a.buyback_pct_of_volume||0,
      maxW: a.max_allowed_week||0, util: a.utilization_pct||0,
    });
  }
  return rows;
}

function render(){
  const rows = calc();
  const R = rows.length ? rows[rows.length-1] : null;
  const kurs = D.current_price || 0;
  const totalOut = R ? R.totalOut : (D.total_shares||199226613);
  const mcapSek = kurs * totalOut;
  const mcapEur = mcapSek / EUR_SEK;
  const progMax = ACTIVE_PROG ? ACTIVE_PROG.max_eur : 0;
  const progSizePctMcap = mcapEur>0 ? progMax/mcapEur*100 : 0;

  document.getElementById('hKrs').textContent = kurs ? f2(kurs) : '—';
  document.getElementById('hMcap').textContent = mcapSek ? fB(mcapSek)+' mia.' : '—';
  document.getElementById('hTr').textContent = R ? fD(R.treasury) : '0';

  const aS = R ? R.aS : 0;
  const aAmtSek = R ? R.aAmt : 0;
  const aAmtEur = aAmtSek / EUR_SEK;
  const progUtilPct = progMax>0 ? aAmtEur/progMax*100 : 0;
  const avgPrice = R ? R.avg : 0;
  const disc = (avgPrice>0 && kurs>0) ? (avgPrice-kurs)/avgPrice*100 : 0;
  const capPct = R ? R.capPct : 0;
  const epsUpliftMax = R && R.totalOut>0 ? R.maxProg/(R.totalOut-R.maxProg)*100 : 0;
  const epsUpliftNow = R && R.totalOut>0 ? R.treasury/(R.totalOut-R.treasury)*100 : 0;

  document.getElementById('kpis').innerHTML = [
    {l:'Tilbagekøbt', v:fD(aS), s:(totalOut>0?(aS/totalOut*100).toFixed(2):'0')+'% af udstedte'},
    {l:'Investeret', v:'SEK '+fM(aAmtSek)+'M', s:'€'+(aAmtEur/1e6).toFixed(0)+'M · '+progUtilPct.toFixed(1)+'% af €2B'},
    {l:'Gns. købskurs', v:'SEK '+(avgPrice?f2(avgPrice):'—'), s:(disc>0?disc.toFixed(1)+'% over kurs':Math.abs(disc).toFixed(1)+'% under kurs')},
    {l:'Andel af udestående', v:(R?R.sharePct:0).toFixed(2)+'%', s:'10%-cap: '+(R?R.maxProg:0).toLocaleString('da-DK')+' aktier', c:'color:var(--g1)'},
    {l:'EPS-løft (nu)', v:'+'+epsUpliftNow.toFixed(2)+'%', s:'ved fuld cap: +'+epsUpliftMax.toFixed(1)+'%', c:'color:var(--g2)'},
    {l:'€2B vs. mkt.værdi', v:progSizePctMcap.toFixed(1)+'%', s:'Implicit buyback yield', c:'color:var(--g3)'},
  ].map(k=>'<div class="kpi"><div class="l">'+k.l+'</div><div class="v" style="'+(k.c||'')+'">'+k.v+'</div><div class="s">'+k.s+'</div></div>').join('');

  document.getElementById('vcG').innerHTML =
    '<div class="vb a"><div class="nm">'+fD(aS)+' stk.</div><div class="lb">Tilbagekøbt til gns.</div><div class="dt">'+(avgPrice?f2(avgPrice):'—')+' SEK/aktie · '+fM(aAmtSek)+'M SEK</div></div>'+
    '<div class="vc-ar">→</div>'+
    '<div class="vb b"><div class="nm" style="color:var(--g2)">+'+epsUpliftNow.toFixed(2)+'%</div><div class="lb">EPS-løft pr. aktie</div><div class="dt">€'+EPS_2025+' → €'+(EPS_2025*(1+epsUpliftNow/100)).toFixed(2)+' ved annullering</div></div>'+
    '<div class="vc-ar">→</div>'+
    '<div class="vb c"><div class="nm" style="color:var(--g4)">-'+(totalOut>0?(aS/totalOut*100):0).toFixed(2)+'%</div><div class="lb">Reduktion i udstedte</div><div class="dt">'+fD(totalOut)+' → '+fD(totalOut-aS)+' aktier</div></div>';
  document.getElementById('mn').textContent =
    'EPS-løft = aktier_tilbagekøbt / (udstedte − tilbagekøbte). Baseret på €'+EPS_2025+' (FY25). 10%-cap = '+fD(R?R.maxProg:0)+' aktier (~'+(R?(R.maxProg/totalOut*100):0).toFixed(1)+'% af udstedte).';

  // Progress bar — defaults to active program only.
  // Dropdown lets user switch to lifetime aggregate view across all programs.
  function renderProgress(mode){
    if (mode === 'all'){
      // Lifetime view: completed programs assumed 100% utilized + active progress
      const totalMaxEur = PROGS.reduce((s,p)=>s+p.max_eur,0);
      let lifetimeEur = 0;
      PROGS.forEach(p=>{ if (p.closed_on) lifetimeEur += p.max_eur; });
      lifetimeEur += aAmtEur;
      const totalPct = totalMaxEur>0 ? lifetimeEur/totalMaxEur*100 : 0;
      document.getElementById('pHdr').textContent = 'Programmer — €'+(totalMaxEur/1e6).toLocaleString('da-DK')+'M total';
      document.getElementById('pF').style.width = Math.min(totalPct,100)+'%';
      document.getElementById('pPct').textContent = totalPct.toFixed(1)+'%';
      document.getElementById('pL').textContent = '€'+(lifetimeEur/1e6).toFixed(0)+'M brugt';
      document.getElementById('pMax').textContent = '€'+(totalMaxEur/1e6).toLocaleString('da-DK')+'M';
      document.getElementById('pDetail').innerHTML = PROGS.map(p=>{
        let used, pct;
        if (p.closed_on) { used = p.max_eur; pct = 100; }
        else if (ACTIVE_PROG && p.id === ACTIVE_PROG.id) { used = aAmtEur; pct = p.max_eur>0?used/p.max_eur*100:0; }
        else { used = 0; pct = 0; }
        const status = p.closed_on
          ? '<span style="color:var(--t3)">Afsluttet</span>'
          : (pct>=99.9 ? '<span style="color:var(--g3)">Afsluttet</span>' : '<span style="color:var(--g2)">Aktivt</span>');
        return '<div>'+p.name+': €'+(used/1e6).toFixed(0)+'M / €'+(p.max_eur/1e6).toFixed(0)+'M ('+pct.toFixed(1)+'%) · '+status+'</div>';
      }).join('');
    } else {
      // Active program only (default) — the meaningful real-time deployment view
      const p = ACTIVE_PROG;
      if (!p){
        document.getElementById('pHdr').textContent = 'Intet aktivt program';
        document.getElementById('pF').style.width = '0%';
        document.getElementById('pPct').textContent = '—';
        document.getElementById('pL').textContent = '—';
        document.getElementById('pMax').textContent = '—';
        document.getElementById('pDetail').innerHTML = '';
        return;
      }
      const used = aAmtEur;
      const pct = p.max_eur>0 ? used/p.max_eur*100 : 0;
      document.getElementById('pHdr').textContent = p.name + ' — annonceret ' + (p.announced||'—');
      document.getElementById('pF').style.width = Math.min(pct,100)+'%';
      document.getElementById('pPct').textContent = pct.toFixed(1)+'%';
      document.getElementById('pL').textContent = '€'+(used/1e6).toFixed(0)+'M brugt · ' + fD(aS) + ' aktier';
      document.getElementById('pMax').textContent = '€'+(p.max_eur/1e6).toLocaleString('da-DK')+'M';
      // Show pace estimate: weeks since start + extrapolated completion
      const startD = new Date(p.start);
      const weeksRunning = Math.max(1, Math.round((Date.now() - startD.getTime()) / (7*24*3600*1000)));
      const eurPerWeek = used / weeksRunning;
      const weeksRemaining = eurPerWeek>0 ? Math.round((p.max_eur - used) / eurPerWeek) : 0;
      const eta = weeksRemaining>0 ? new Date(Date.now() + weeksRemaining*7*24*3600*1000) : null;
      document.getElementById('pDetail').innerHTML =
        '<div>Tempo: €'+(eurPerWeek/1e6).toFixed(0)+'M/uge (gns. ' + weeksRunning + ' uge'+(weeksRunning!==1?'r':'')+')</div>' +
        (eta ? '<div>Estimeret afslutning: '+eta.toLocaleDateString('da-DK',{month:'short',year:'numeric'})+' (' + weeksRemaining + ' uger tilbage)</div>' : '');
    }
  }
  renderProgress('active');
  document.getElementById('pSel').addEventListener('change', e => renderProgress(e.target.value));

  const lbl = rows.map(r=>new Date(r.d).toLocaleDateString('da-DK',{day:'numeric',month:'short'}));
  const cO=(x)=>{x=x||{};return{responsive:true,maintainAspectRatio:false,
    plugins:{legend:{display:false,...(x.lg||{})},
      tooltip:{backgroundColor:'#1a2230',titleFont:{family:'JetBrains Mono',size:11},
        bodyFont:{family:'JetBrains Mono',size:11},borderColor:'#3d4a5c',borderWidth:1,
        titleColor:'#f8fafc',bodyColor:'#b0bac9',padding:8,cornerRadius:3,
        callbacks:{label:c=>{let v=c.parsed.y;return(c.dataset.label?c.dataset.label+': ':'')+((c.dataset.pct)?v.toFixed(1)+'%':v>=1e9?fB(v)+' mia.':v>=1e6?fM(v)+' mio.':v>=1e3?fK(v)+'K':v.toFixed(2))}}}},
    scales:{
      x:{ticks:{color:'#b0bac9',font:{family:'JetBrains Mono',size:10},maxRotation:45},grid:{color:'rgba(61,74,92,.35)'}},
      y:{ticks:{color:'#b0bac9',font:{family:'JetBrains Mono',size:10},
        callback:v=>v>=1e9?(v/1e9).toFixed(1)+'B':v>=1e6?(v/1e6).toFixed(1)+'M':v>=1e3?(v/1e3).toFixed(0)+'K':v,...(x.yt||{})},
        grid:{color:'rgba(61,74,92,.35)'},...(x.y||{})}}};};

  if (!rows.length){
    ['ch1','ch2','ch3','ch4','ch5'].forEach(id=>{
      const cv=document.getElementById(id); const ctx=cv.getContext('2d');
      ctx.fillStyle='#6b7a90';ctx.font='12px JetBrains Mono';
      ctx.textAlign='center';ctx.fillText('Venter på første ugentlige rapport', cv.width/2, 100);
    });
  } else {
    const priceData = rows.map(r=>Math.round(r.wA*100)/100);
    const kursLine = rows.map(()=>kurs);
    new Chart(document.getElementById('ch1'),{type:'line',data:{labels:lbl,datasets:[
      {label:'Aktuel kurs',data:kursLine,borderColor:'#34d399',borderWidth:1.5,borderDash:[5,3],pointRadius:0,fill:false},
      {label:'Tilbagekøbskurs',data:priceData,borderColor:'#f8fafc',backgroundColor:'rgba(248,250,252,.04)',borderWidth:2,fill:true,tension:.3,pointRadius:2.5,pointBackgroundColor:'#f8fafc'}
    ]},options:cO({lg:{display:true,labels:{color:'#b0bac9',font:{family:'JetBrains Mono',size:10},boxWidth:10,padding:12}}})});

    new Chart(document.getElementById('ch2'),{type:'line',data:{labels:lbl,datasets:[{
      label:'% af udestående',data:rows.map(r=>Math.round(r.sharePct*100)/100),
      borderColor:'#10b981',backgroundColor:'rgba(16,185,129,.06)',borderWidth:2,fill:true,tension:.3,
      pointRadius:2.5,pointBackgroundColor:'#10b981',pct:true
    }]},options:cO({y:{beginAtZero:true,suggestedMax:Math.max(2, Math.ceil((rows[rows.length-1].sharePct||0) * 1.8 * 10)/10)},yt:{callback:v=>v+'%'}})});

    new Chart(document.getElementById('ch3'),{type:'line',data:{labels:lbl,datasets:[{
      label:'Forbrug',data:rows.map(r=>Math.round(r.aAmt)),
      borderColor:'#059669',backgroundColor:'rgba(5,150,105,.08)',borderWidth:2,fill:true,tension:.3,
      pointRadius:2.5,pointBackgroundColor:'#059669'
    }]},options:cO()});

    const hasMktVol = rows.some(r=>r.mVol>0);
    const volData = rows.map(r=>r.mVol);
    const buyData = rows.map(r=>r.wS);
    const ch4ds = [{label:'Tilbagekøbt',data:buyData,backgroundColor:'rgba(248,250,252,.25)',borderColor:'rgba(248,250,252,.4)',borderWidth:1,borderRadius:2}];
    if (hasMktVol){
      ch4ds.unshift({label:'Markedsvolumen',data:volData,backgroundColor:'rgba(176,186,201,.1)',borderColor:'rgba(176,186,201,.2)',borderWidth:1,borderRadius:2});
    }
    new Chart(document.getElementById('ch4'),{type:'bar',data:{labels:lbl,datasets:ch4ds},
      options:cO({y:{beginAtZero:true},lg:{display:hasMktVol,labels:{color:'#b0bac9',font:{family:'JetBrains Mono',size:10},boxWidth:10,padding:12}}})});

    if (hasMktVol){
      // Safe Harbour utilization: faktisk købt / max tilladt (25% × 20-day ADV × handelsdage) × 100.
      // The 25% rule is DAILY against 20-day ADV — utilization_pct (Tempo) is the legally correct
      // compliance metric. 100% = exactly at the ceiling every trading day.
      const utilData = rows.map(r=>r.util);
      const utilColors = utilData.map(p=>p>100?'rgba(239,68,68,.6)':p>80?'rgba(245,158,11,.6)':'rgba(16,185,129,.5)');
      const limitLine = utilData.map(()=>100);
      // For reference: also show weekly % of volume (informational, not regulatory)
      const pctData = rows.map(r=>r.bPct);
      new Chart(document.getElementById('ch5'),{type:'bar',data:{labels:lbl,datasets:[
        {label:'Safe Harbour-udnyttelse',data:utilData,backgroundColor:utilColors,borderColor:utilColors.map(c=>c.replace(/[\d.]+\)$/,'0.8)')),borderWidth:1,borderRadius:2,pct:true,order:3},
        {label:'100% loft (25% × 20-d gns. ADV pr. dag)',data:limitLine,type:'line',borderColor:'#f59e0b',borderWidth:1.5,borderDash:[8,4],pointRadius:0,fill:false,pct:true,order:1},
        {label:'% af ugens markedsvolumen',data:pctData,type:'line',borderColor:'#b0bac9',borderWidth:1.5,borderDash:[4,3],pointRadius:2,tension:.3,fill:false,pct:true,order:2}
      ]},options:cO({y:{beginAtZero:true,suggestedMax:Math.max(120, Math.ceil(Math.max(...utilData) * 1.2))},yt:{callback:v=>v+'%'},
        lg:{display:true,labels:{color:'#b0bac9',font:{family:'JetBrains Mono',size:10},boxWidth:10,padding:12}}})});
    } else {
      const cv5=document.getElementById('ch5'); const ctx5=cv5.getContext('2d');
      ctx5.fillStyle='#6b7a90';ctx5.font='12px JetBrains Mono';
      ctx5.textAlign='center';ctx5.fillText('Volume-data hentes ved næste opdatering', cv5.width/2, 80);
    }
  }

  const cols=[
    {k:'i',l:'#',left:true},
    {k:'d',l:'Periode',left:true},
    {k:'wS',l:'Købt'},
    {k:'wA',l:'Kurs'},
    {k:'wAmt',l:'Beløb'},
    {k:'mVol',l:'Mkt.vol'},
    {k:'bPct',l:'% af vol'},
    {k:'util',l:'Tempo'},
    {k:'aS',l:'Akk.stk'},
    {k:'aAmt',l:'Akk.SEK'},
    {k:'treasury',l:'Treasury'},
    {k:'capPct',l:'% af cap'},
  ];

  let sortCol='i', sortDir='desc';

  function renderTable(){
    const sorted=[...rows];
    sorted.sort((a,b)=>{
      let va=a[sortCol],vb=b[sortCol];
      if(typeof va==='string')return sortDir==='asc'?va.localeCompare(vb):vb.localeCompare(va);
      return sortDir==='asc'?(va-vb):(vb-va);
    });
    document.querySelectorAll('#tbl th').forEach((th,ci)=>{
      const col=cols[ci]; const isActive=col.k===sortCol;
      th.className=isActive?'active':'';
      th.innerHTML=col.l + '<span class="arrow">'+(isActive?(sortDir==='desc'?'▼':'▲'):'⇅')+'</span>';
      if(col.left)th.style.textAlign='left';
    });
    document.getElementById('tb').innerHTML=sorted.map(r=>{
      const periode = new Date(r.ps).toLocaleDateString('da-DK',{day:'numeric',month:'short'}) + ' – ' + new Date(r.d).toLocaleDateString('da-DK',{day:'numeric',month:'short'});
      return '<tr>'+
        '<td>'+r.i+'</td>'+
        '<td>'+periode+'</td>'+
        '<td>'+fD(r.wS)+'</td>'+
        '<td>'+f2(r.wA)+'</td>'+
        '<td>'+fK(r.wAmt)+'K</td>'+
        '<td>'+(r.mVol>0?fD(r.mVol):'—')+'</td>'+
        '<td style="color:'+(r.bPct>40?'var(--red)':r.bPct>20?'var(--amb)':'var(--g3)')+'">'+(r.bPct>0?r.bPct.toFixed(1)+'%':'—')+'</td>'+
        '<td style="color:'+(r.util>100?'var(--red)':r.util>80?'var(--g3)':r.util>50?'var(--amb)':r.util>0?'var(--red)':'var(--t3)')+'">'+(r.util>0?r.util.toFixed(0)+'%':'—')+'</td>'+
        '<td><b>'+fD(r.aS)+'</b></td>'+
        '<td>'+fM(r.aAmt)+'M</td>'+
        '<td>'+fD(r.treasury)+'</td>'+
        '<td style="color:var(--g1)">'+r.capPct.toFixed(1)+'%</td>'+
      '</tr>';
    }).join('');
  }
  const thead=document.getElementById('tbl').querySelector('thead tr');
  thead.innerHTML='';
  cols.forEach(col=>{
    const th=document.createElement('th');
    if(col.left)th.style.textAlign='left';
    th.addEventListener('click',()=>{
      if(sortCol===col.k){sortDir=sortDir==='desc'?'asc':'desc';}
      else{sortCol=col.k;sortDir='desc';}
      renderTable();
    });
    thead.appendChild(th);
  });
  renderTable();

  document.getElementById('upd').textContent='Sidst: '+(D.last_updated?new Date(D.last_updated).toLocaleDateString('da-DK',{day:'numeric',month:'short',year:'numeric'}):'—');
}
render();
</script>
</body>
</html>"""


if __name__ == "__main__":
    build()

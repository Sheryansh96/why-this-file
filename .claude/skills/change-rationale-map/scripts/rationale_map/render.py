"""
render.py — turn graph.json (from graph.build_graph) into a standalone,
interactive HTML visualization. Agent-neutral: only ever reads graph.json,
never a raw transcript.
"""
import json
from pathlib import Path

D3_PATH = Path(__file__).parent / "d3.min.js"

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Change Rationale Map</title>
<script>__D3_JS__</script>
<style>
  :root{
    --bg:#12151A; --panel:#1A1E26; --panel-2:#20242D; --line:#2B303B;
    --text:#E7E9EC; --muted:#8B93A1; --dim:#5A6270;
    --write:#E8A33D; --read:#4FA3D1; --ref:#5D6472;
    --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
    --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif;
  }
  *{box-sizing:border-box;}
  body{margin:0; background:var(--bg); color:var(--text); font-family:var(--sans); overflow:hidden;}
  #app{display:grid; grid-template-columns: 300px 1fr 340px; grid-template-rows: 56px 1fr; height:100vh;}
  header{grid-column:1/4; display:flex; align-items:center; justify-content:space-between; padding:0 20px; border-bottom:1px solid var(--line); background:var(--panel);}
  header .title{font-size:14px; letter-spacing:.04em; color:var(--text); font-weight:600;}
  header .title .dim{color:var(--dim); font-weight:400;}
  header .stats{display:flex; gap:18px; font-family:var(--mono); font-size:11px; color:var(--muted);}
  header .stats b{color:var(--text); font-weight:600;}
  #sidebar{grid-column:1; grid-row:2; border-right:1px solid var(--line); overflow-y:auto; padding:14px 0;}
  #sidebar .section-label{font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--dim); padding:6px 16px; margin-top:6px;}
  .file-row{display:flex; align-items:center; gap:8px; padding:7px 16px; cursor:pointer; border-left:2px solid transparent; font-family:var(--mono); font-size:12px; color:var(--muted);}
  .file-row:hover{background:var(--panel-2); color:var(--text);}
  .file-row.active{background:var(--panel-2); border-left-color:var(--write); color:var(--text);}
  .file-row .dot{width:6px; height:6px; border-radius:50%; flex-shrink:0;}
  .file-row .count{margin-left:auto; color:var(--dim); font-size:10px;}
  #canvas-wrap{grid-column:2; grid-row:2; position:relative; overflow:hidden;}
  #timeline-wrap{grid-column:2; grid-row:2;}
  #canvas-wrap svg{width:100%; height:100%; display:block;}
  .lane-guide{stroke:var(--line); stroke-width:1.5;}
  .lane-label{fill:var(--muted); font-family:var(--mono); font-size:11px;}
  .turn-tick{stroke:var(--line); stroke-width:1; stroke-dasharray:2,3; opacity:.7;}
  .turn-tick-label{fill:var(--dim); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:.04em;}
  .touch-dot{stroke:var(--bg); stroke-width:1.5; cursor:pointer;}
  .touch-dot.write{fill:var(--write);}
  .touch-dot.read{fill:var(--read);}
  .touch-dot.active{stroke:var(--text); stroke-width:2; r:7;}
  .touch-dot.dim{opacity:.2;}
  .edge{fill:none; stroke-width:1.4;}
  .edge.same-turn{stroke:var(--write); opacity:.6;}
  .edge.referenced{stroke:var(--ref); stroke-dasharray:2,3; opacity:.65;}
  .edge.dim{opacity:.06;}
  .legend{position:absolute; left:14px; bottom:14px; font-family:var(--mono); font-size:10px; color:var(--muted); background:var(--panel); border:1px solid var(--line); padding:10px 12px; border-radius:6px; line-height:1.9;}
  .legend .sw{display:inline-block; width:14px; height:2px; margin-right:6px; vertical-align:middle;}
  #detail{grid-column:3; grid-row:2; border-left:1px solid var(--line); padding:18px 18px; overflow-y:auto;}
  #detail .empty{color:var(--dim); font-size:12px; margin-top:40px; text-align:center; line-height:1.6;}
  #detail .file-path{font-family:var(--mono); font-size:12px; color:var(--text); word-break:break-all; line-height:1.5; padding-bottom:10px; border-bottom:1px solid var(--line); margin-bottom:14px;}
  #detail .badge-row{display:flex; gap:6px; margin-top:8px;}
  .badge{font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:.05em; padding:2px 7px; border-radius:3px; border:1px solid var(--line); color:var(--muted);}
  .badge.write{color:var(--write); border-color:#4A3A20;}
  .badge.read{color:var(--read); border-color:#20384A;}
  .timeline-item{position:relative; padding:0 0 18px 18px; border-left:1px solid var(--line);}
  .timeline-item:last-child{border-left-color:transparent; padding-bottom:0;}
  .timeline-item::before{content:''; position:absolute; left:-4px; top:2px; width:7px; height:7px; border-radius:50%; background:var(--dim); border:2px solid var(--panel);}
  .timeline-item.write::before{background:var(--write);}
  .timeline-item.read::before{background:var(--read);}
  .timeline-meta{font-family:var(--mono); font-size:9px; color:var(--dim); text-transform:uppercase; letter-spacing:.05em; margin-bottom:4px;}
  .timeline-reason{font-size:12.5px; color:var(--text); line-height:1.55;}
  .timeline-reason.none{color:var(--dim); font-style:italic;}
  #detail .section-label{font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--dim); margin:18px 0 10px;}
  ::-webkit-scrollbar{width:8px;} ::-webkit-scrollbar-thumb{background:var(--line); border-radius:4px;}

  .view-toggle{display:flex; gap:2px; background:var(--panel-2); border:1px solid var(--line); border-radius:6px; padding:2px;}
  .view-toggle button{
    font-family:var(--mono); font-size:11px; color:var(--muted); background:transparent; border:none;
    padding:5px 12px; border-radius:4px; cursor:pointer; letter-spacing:.02em;
  }
  .view-toggle button.active{background:var(--panel); color:var(--text);}
  .view-toggle button:hover:not(.active){color:var(--text);}

  #timeline-wrap{height:100%; overflow-y:auto; padding:22px 28px 60px;}
  #timeline-wrap.hidden, #canvas-wrap.hidden{display:none;}
  .tl-turn-head{
    display:flex; align-items:center; gap:10px; margin:26px 0 12px; font-family:var(--mono);
  }
  .tl-turn-head:first-child{margin-top:0;}
  .tl-turn-head .tl-turn-label{
    font-size:10px; letter-spacing:.1em; color:var(--dim); text-transform:uppercase; white-space:nowrap;
  }
  .tl-turn-head::after{content:''; flex:1; height:1px; background:var(--line);}
  .tl-row{
    display:grid; grid-template-columns:22px 1fr; gap:12px; padding:10px 12px; margin-bottom:4px;
    border-radius:6px; cursor:pointer; border:1px solid transparent;
  }
  .tl-row:hover{background:var(--panel-2);}
  .tl-row.active{background:var(--panel-2); border-color:var(--write);}
  .tl-rail{display:flex; flex-direction:column; align-items:center;}
  .tl-dot{width:9px; height:9px; border-radius:50%; margin-top:3px; flex-shrink:0;}
  .tl-dot.write{background:var(--write);}
  .tl-dot.read{background:var(--read);}
  .tl-line{width:1px; flex:1; background:var(--line); margin-top:4px;}
  .tl-row:last-child .tl-line{display:none;}
  .tl-head-row{display:flex; align-items:baseline; gap:8px; flex-wrap:wrap;}
  .tl-file{font-family:var(--mono); font-size:12.5px; color:var(--text); font-weight:600;}
  .tl-tool{font-family:var(--mono); font-size:9.5px; color:var(--dim); text-transform:uppercase; letter-spacing:.04em;}
  .tl-reason{font-size:12.5px; color:var(--muted); line-height:1.55; margin-top:4px;}
  .tl-reason.none{font-style:italic; color:var(--dim);}
</style>
</head>
<body>
<div id="app">
  <header>
    <div class="title">Change Rationale Map <span class="dim">/ __GRAPH_TITLE__</span></div>
    <div class="view-toggle" id="view-toggle">
      <button data-view="timeline" class="active">Timeline</button>
      <button data-view="graph">Graph</button>
    </div>
    <div class="stats">
      <span><b id="stat-files">0</b> files touched</span>
      <span><b id="stat-turns">0</b> turns</span>
      <span><b id="stat-edges">0</b> traces</span>
    </div>
  </header>
  <div id="sidebar">
    <div class="section-label">Files (by first touch)</div>
    <div id="file-list"></div>
  </div>
  <div id="timeline-wrap"></div>
  <div id="canvas-wrap" class="hidden">
    <svg id="graph"></svg>
    <div class="legend">
      <div><span class="sw" style="background:var(--write)"></span>same-turn causality</div>
      <div><span class="sw" style="background:var(--ref); border-top:2px dashed var(--ref); height:0;"></span>referenced in reasoning</div>
      <div style="margin-top:6px;"><span class="sw" style="background:var(--write); height:8px; border-radius:2px;"></span>write &nbsp;&nbsp;<span class="sw" style="background:var(--read); height:8px; border-radius:2px;"></span>read-only</div>
    </div>
  </div>
  <div id="detail"><div class="empty">Click a step in the timeline — or a file in the graph or the list — to see it here.</div></div>
</div>

<script>
const graph = __GRAPH_JSON__;

document.getElementById('stat-files').textContent = graph.nodes.length;
document.getElementById('stat-edges').textContent = graph.edges.length;
const allTurns = new Set();
graph.nodes.forEach(n => n.turns.forEach(t => allTurns.add(t)));
document.getElementById('stat-turns').textContent = allTurns.size;

// ---- sidebar ----
const fileList = document.getElementById('file-list');
const sortedNodes = [...graph.nodes].sort((a,b) => (a.timeline[0]?.turn ?? 0) - (b.timeline[0]?.turn ?? 0));
sortedNodes.forEach(n => {
  const row = document.createElement('div');
  row.className = 'file-row';
  row.dataset.id = n.id;
  const isWrite = n.actions.includes('write');
  row.innerHTML = `<span class="dot" style="background:${isWrite ? 'var(--write)' : 'var(--read)'}"></span>
                    <span title="${n.id}">${n.label}</span>
                    <span class="count">${n.touch_count}×</span>`;
  row.onclick = () => selectNode(n.id);
  fileList.appendChild(row);
});

// ---- timeline (default view): every touch, in the order it happened ----
const timelineWrap = document.getElementById('timeline-wrap');
const sequence = graph.sequence || [];

function renderTimeline(){
  timelineWrap.innerHTML = '';
  let lastTurn = null;
  sequence.forEach((t, i) => {
    if (t.turn !== lastTurn) {
      lastTurn = t.turn;
      const head = document.createElement('div');
      head.className = 'tl-turn-head';
      head.innerHTML = `<span class="tl-turn-label">Turn ${t.turn}</span>`;
      timelineWrap.appendChild(head);
    }
    const row = document.createElement('div');
    row.className = 'tl-row';
    row.dataset.id = t.file;
    row.innerHTML = `
      <div class="tl-rail"><span class="tl-dot ${t.action}"></span><span class="tl-line"></span></div>
      <div>
        <div class="tl-head-row">
          <span class="tl-file">${t.label}</span>
          <span class="tl-tool">${t.action} · ${t.tool}</span>
        </div>
        <div class="tl-reason ${t.reasoning ? '' : 'none'}">${t.reasoning || 'no explicit reasoning captured before this call'}</div>
      </div>`;
    row.onclick = () => selectNode(t.file);
    timelineWrap.appendChild(row);
  });
}
renderTimeline();

// ---- graph: a sequential lane diagram, not a physics simulation ----
// x = when it happened (touch order, left to right); y = which file (a fixed
// lane, ordered by first touch, top to bottom). Position IS the timeline —
// nothing moves or settles, so there's nothing to read except the layout.
const svg = d3.select('#graph');
const wrap = document.getElementById('canvas-wrap');
const g = svg.append('g');
svg.call(d3.zoom().scaleExtent([0.3, 4]).on('zoom', (ev) => g.attr('transform', ev.transform)));

svg.append('defs').append('marker')
  .attr('id','arrow').attr('viewBox','0 -4 8 8').attr('refX', 7).attr('refY',0)
  .attr('markerWidth',6).attr('markerHeight',6).attr('orient','auto')
  .append('path').attr('d','M0,-4L8,0L0,4').attr('fill','var(--write)').attr('opacity',0.8);

const laneOrder = sortedNodes.map(n => n.id);           // top-to-bottom, by first touch
const laneIndex = new Map(laneOrder.map((id,i) => [id,i]));
const laneHeight = 42, marginTop = 44, marginLeft = 190, marginRight = 40;
const maxOrder = Math.max(1, ...sequence.map(t => t.order));
const touchesOf = new Map(laneOrder.map(id => [id, sequence.filter(t => t.file === id)]));

let xScale, nodeSel, edgeSel;

// for a "same-turn" edge, anchor it at a turn the two files actually shared;
// for a "referenced" edge (no shared-turn guarantee), anchor at the target's
// first touch and the nearest source touch at or before it.
function anchorsFor(e){
  if (e.type === 'same-turn') {
    const turnsOfSource = new Map();
    touchesOf.get(e.source).forEach(t => { if (!turnsOfSource.has(t.turn)) turnsOfSource.set(t.turn, t); });
    const shared = touchesOf.get(e.target).find(t => turnsOfSource.has(t.turn));
    if (shared) return [turnsOfSource.get(shared.turn), shared];
  }
  const targetTouch = touchesOf.get(e.target)[0] || touchesOf.get(e.source)[0];
  const before = touchesOf.get(e.source).filter(t => t.order <= targetTouch.order);
  const sourceTouch = before.length ? before[before.length - 1] : touchesOf.get(e.source)[0];
  return [sourceTouch, targetTouch];
}

function edgePath(e){
  const [a, b] = anchorsFor(e);
  const x1 = xScale(a.order), y1 = marginTop + laneIndex.get(a.file) * laneHeight;
  const x2 = xScale(b.order), y2 = marginTop + laneIndex.get(b.file) * laneHeight;
  const xm = (x1 + x2) / 2;
  return `M${x1},${y1} C${xm},${y1} ${xm},${y2} ${x2},${y2}`;
}

function renderGraph(){
  const width = Math.max(wrap.clientWidth, 200);
  const plotWidth = Math.max(160, width - marginLeft - marginRight);
  xScale = d3.scaleLinear().domain([1, maxOrder]).range([marginLeft, marginLeft + plotWidth]);
  const totalHeight = marginTop + laneOrder.length * laneHeight + 24;
  svg.attr('viewBox', [0, 0, width, Math.max(wrap.clientHeight, totalHeight)]);
  g.selectAll('*').remove();

  // lanes: guide line spanning each file's own first→last touch, + label
  const laneG = g.append('g');
  sortedNodes.forEach((n, i) => {
    const touches = touchesOf.get(n.id);
    const y = marginTop + i * laneHeight;
    laneG.append('line').attr('class', 'lane-guide')
      .attr('x1', xScale(touches[0].order)).attr('x2', xScale(touches[touches.length - 1].order))
      .attr('y1', y).attr('y2', y);
    laneG.append('text').attr('class', 'lane-label')
      .attr('x', marginLeft - 14).attr('y', y + 4).attr('text-anchor', 'end')
      .text(n.label).append('title').text(n.id);
  });

  // turn axis: one dashed vertical line + label per turn, at its first touch
  const turnG = g.append('g');
  const seenTurns = new Set();
  sequence.forEach(t => {
    if (seenTurns.has(t.turn)) return;
    seenTurns.add(t.turn);
    const x = xScale(t.order);
    turnG.append('line').attr('class', 'turn-tick')
      .attr('x1', x).attr('x2', x).attr('y1', marginTop - 20).attr('y2', marginTop + laneOrder.length * laneHeight - laneHeight/2);
    turnG.append('text').attr('class', 'turn-tick-label')
      .attr('x', x).attr('y', marginTop - 26).attr('text-anchor', 'middle')
      .text('T' + t.turn);
  });

  edgeSel = g.append('g').selectAll('path')
    .data(graph.edges).join('path')
    .attr('class', d => 'edge ' + d.type)
    .attr('marker-end', d => d.type === 'same-turn' ? 'url(#arrow)' : null)
    .attr('d', edgePath);

  nodeSel = g.append('g').selectAll('circle.touch-dot')
    .data(sequence).join('circle')
    .attr('class', d => 'touch-dot ' + d.action)
    .attr('r', 5)
    .attr('cx', d => xScale(d.order))
    .attr('cy', d => marginTop + laneIndex.get(d.file) * laneHeight)
    .on('click', (ev, d) => selectNode(d.file))
    .append('title').text(d => `turn ${d.turn} · ${d.action} · ${d.tool}`);
  nodeSel = g.selectAll('circle.touch-dot'); // re-grab: .append('title') above returns the titles, not the circles
}
window.addEventListener('resize', () => { if (!wrap.classList.contains('hidden')) renderGraph(); });

let selected = null;
function selectNode(id){
  selected = id;
  document.querySelectorAll('.file-row').forEach(r => r.classList.toggle('active', r.dataset.id === id));
  document.querySelectorAll('.tl-row').forEach(r => r.classList.toggle('active', r.dataset.id === id));
  if (nodeSel) nodeSel.classed('active', d => d.file === id).classed('dim', d => d.file !== id);
  if (edgeSel) edgeSel.classed('dim', d => d.source !== id && d.target !== id);
  renderDetail(id);
}

function renderDetail(id){
  const n = graph.nodes.find(x => x.id === id);
  const panel = document.getElementById('detail');
  if(!n){ panel.innerHTML = '<div class="empty">No file selected.</div>'; return; }
  const badges = n.actions.map(a => `<span class="badge ${a}">${a}</span>`).join('');
  const items = n.timeline.map(t => `
    <div class="timeline-item ${t.action}">
      <div class="timeline-meta">turn ${t.turn} · ${t.tool}</div>
      <div class="timeline-reason ${t.reasoning ? '' : 'none'}">${t.reasoning || 'no explicit reasoning captured before this call'}</div>
    </div>`).join('');
  panel.innerHTML = `
    <div class="file-path">${n.id}<div class="badge-row">${badges}</div></div>
    <div class="section-label">Why this file was touched</div>
    ${items}
  `;
}

// ---- view toggle: the lane graph starts hidden (0×0), so it needs one
// real layout pass once it's actually shown, not just on window resize ----
const viewToggle = document.getElementById('view-toggle');
let graphEverShown = false;
viewToggle.addEventListener('click', (ev) => {
  const btn = ev.target.closest('button[data-view]');
  if (!btn) return;
  const view = btn.dataset.view;
  viewToggle.querySelectorAll('button').forEach(b => b.classList.toggle('active', b === btn));
  timelineWrap.classList.toggle('hidden', view !== 'timeline');
  wrap.classList.toggle('hidden', view !== 'graph');
  if (view === 'graph' && !graphEverShown) {
    graphEverShown = true;
    renderGraph();
    if (selected) selectNode(selected);
  }
});
</script>
</body>
</html>
"""


def render(graph_data, title="session"):
    d3_js = D3_PATH.read_text() if D3_PATH.exists() else ""
    return (
        TEMPLATE.replace("__GRAPH_JSON__", json.dumps(graph_data))
        .replace("__GRAPH_TITLE__", title)
        .replace("__D3_JS__", d3_js)
    )

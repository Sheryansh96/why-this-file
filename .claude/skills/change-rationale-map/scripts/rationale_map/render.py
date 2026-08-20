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
  #sidebar{border-right:1px solid var(--line); overflow-y:auto; padding:14px 0;}
  #sidebar .section-label{font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--dim); padding:6px 16px; margin-top:6px;}
  .file-row{display:flex; align-items:center; gap:8px; padding:7px 16px; cursor:pointer; border-left:2px solid transparent; font-family:var(--mono); font-size:12px; color:var(--muted);}
  .file-row:hover{background:var(--panel-2); color:var(--text);}
  .file-row.active{background:var(--panel-2); border-left-color:var(--write); color:var(--text);}
  .file-row .dot{width:6px; height:6px; border-radius:50%; flex-shrink:0;}
  .file-row .count{margin-left:auto; color:var(--dim); font-size:10px;}
  #canvas-wrap{position:relative; overflow:hidden;}
  #canvas-wrap svg{width:100%; height:100%; display:block;}
  .node-rect{fill:var(--panel-2); stroke:var(--line); stroke-width:1; rx:4;}
  .node-rect.active{stroke:var(--write); stroke-width:1.5;}
  .node-bar{}
  .node-label{fill:var(--text); font-family:var(--mono); font-size:11px; pointer-events:none;}
  .node-sub{fill:var(--dim); font-family:var(--mono); font-size:9px; pointer-events:none;}
  .edge{fill:none; stroke-width:1.4;}
  .edge.same-turn{stroke:var(--write); opacity:.55;}
  .edge.referenced{stroke:var(--ref); stroke-dasharray:2,3; opacity:.6;}
  .edge.dim{opacity:.08;}
  .legend{position:absolute; left:14px; bottom:14px; font-family:var(--mono); font-size:10px; color:var(--muted); background:var(--panel); border:1px solid var(--line); padding:10px 12px; border-radius:6px; line-height:1.9;}
  .legend .sw{display:inline-block; width:14px; height:2px; margin-right:6px; vertical-align:middle;}
  #detail{border-left:1px solid var(--line); padding:18px 18px; overflow-y:auto;}
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
</style>
</head>
<body>
<div id="app">
  <header>
    <div class="title">Change Rationale Map <span class="dim">/ __GRAPH_TITLE__</span></div>
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
  <div id="canvas-wrap">
    <svg id="graph"></svg>
    <div class="legend">
      <div><span class="sw" style="background:var(--write)"></span>same-turn causality</div>
      <div><span class="sw" style="background:var(--ref); border-top:2px dashed var(--ref); height:0;"></span>referenced in reasoning</div>
      <div style="margin-top:6px;"><span class="sw" style="background:var(--write); height:8px; border-radius:2px;"></span>write &nbsp;&nbsp;<span class="sw" style="background:var(--read); height:8px; border-radius:2px;"></span>read-only</div>
    </div>
  </div>
  <div id="detail"><div class="empty">Click a file — in the graph or the list — to see why it was touched, in the order it happened.</div></div>
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

// ---- graph ----
const svg = d3.select('#graph');
const wrap = document.getElementById('canvas-wrap');
let width = wrap.clientWidth, height = wrap.clientHeight;
svg.attr('viewBox', [0,0,width,height]);

const g = svg.append('g');
svg.call(d3.zoom().scaleExtent([0.3, 3]).on('zoom', (ev) => g.attr('transform', ev.transform)));

svg.append('defs').append('marker')
  .attr('id','arrow').attr('viewBox','0 -4 8 8').attr('refX', 22).attr('refY',0)
  .attr('markerWidth',6).attr('markerHeight',6).attr('orient','auto')
  .append('path').attr('d','M0,-4L8,0L0,4').attr('fill','var(--write)').attr('opacity',0.7);

const nodeW = d => Math.max(90, d.label.length * 6.6 + 22);
const nodeH = 34;

const sim = d3.forceSimulation(graph.nodes)
  .force('link', d3.forceLink(graph.edges).id(d => d.id).distance(150).strength(0.35))
  .force('charge', d3.forceManyBody().strength(-420))
  .force('center', d3.forceCenter(width/2, height/2))
  .force('collide', d3.forceCollide().radius(d => nodeW(d)/2 + 24));

const edgeSel = g.append('g').selectAll('path')
  .data(graph.edges).join('path')
  .attr('class', d => 'edge ' + d.type)
  .attr('marker-end', d => d.type === 'same-turn' ? 'url(#arrow)' : null);

const nodeSel = g.append('g').selectAll('g.node')
  .data(graph.nodes).join('g')
  .attr('class','node')
  .style('cursor','pointer')
  .call(d3.drag()
    .on('start', (ev,d) => { if(!ev.active) sim.alphaTarget(0.25).restart(); d.fx=d.x; d.fy=d.y; })
    .on('drag', (ev,d) => { d.fx=ev.x; d.fy=ev.y; })
    .on('end', (ev,d) => { if(!ev.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }))
  .on('click', (ev,d) => selectNode(d.id));

nodeSel.append('rect')
  .attr('class','node-rect')
  .attr('width', d => nodeW(d)).attr('height', nodeH)
  .attr('x', d => -nodeW(d)/2).attr('y', -nodeH/2)
  .attr('rx', 4);

nodeSel.append('rect')
  .attr('class','node-bar')
  .attr('width', d => nodeW(d)).attr('height', 3)
  .attr('x', d => -nodeW(d)/2).attr('y', -nodeH/2)
  .attr('fill', d => d.actions.includes('write') ? 'var(--write)' : 'var(--read)');

nodeSel.append('text')
  .attr('class','node-label')
  .attr('text-anchor','middle').attr('y', -2)
  .text(d => d.label);

nodeSel.append('text')
  .attr('class','node-sub')
  .attr('text-anchor','middle').attr('y', 11)
  .text(d => `${d.touch_count}× · turn ${d.turns[0]}`);

function linkPath(d){
  const dx = d.target.x - d.source.x, dy = d.target.y - d.source.y;
  const dr = Math.sqrt(dx*dx+dy*dy) * 1.4;
  return `M${d.source.x},${d.source.y}A${dr},${dr} 0 0,1 ${d.target.x},${d.target.y}`;
}

sim.on('tick', () => {
  edgeSel.attr('d', linkPath);
  nodeSel.attr('transform', d => `translate(${d.x},${d.y})`);
});

let selected = null;
function selectNode(id){
  selected = id;
  document.querySelectorAll('.file-row').forEach(r => r.classList.toggle('active', r.dataset.id === id));
  nodeSel.select('rect.node-rect').classed('active', d => d.id === id);
  edgeSel.classed('dim', d => d.source.id !== id && d.target.id !== id);
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

window.addEventListener('resize', () => {
  width = wrap.clientWidth; height = wrap.clientHeight;
  svg.attr('viewBox', [0,0,width,height]);
  sim.force('center', d3.forceCenter(width/2, height/2));
  sim.alpha(0.3).restart();
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

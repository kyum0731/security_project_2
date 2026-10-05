"""Offline SVG explorer with a hash-authorized script and inert escaped data."""

import base64
import hashlib
import json

from ..graph import graph_data

STYLE = """
.graph-controls{display:flex;flex-wrap:wrap;gap:12px;align-items:end}.graph-controls label{display:grid;gap:5px;font-size:13px}.graph-controls input,.graph-controls select,.graph-controls button,.graph-actions button{font:inherit;padding:8px;border:1px solid #abc8bd;border-radius:6px;background:white;color:#17312e}.graph-controls select{max-width:340px}.graph-controls button,.graph-actions button{cursor:pointer}.graph-layout{display:grid;grid-template-columns:minmax(0,2fr) minmax(230px,1fr);gap:18px;margin-top:16px}.graph-canvas{overflow:auto;border:1px solid #d5e4df;background:#f8fbf9;border-radius:10px;max-height:650px}.graph-canvas svg{width:100%;min-width:650px;display:block}.graph-detail{max-height:650px;overflow:auto;overflow-wrap:anywhere}.graph-node{cursor:pointer}.graph-node:focus rect{stroke:#d58320;stroke-width:4}.graph-edge{cursor:pointer}.graph-edge:focus path{stroke-width:5}.graph-detail li{font-size:13px}.graph-actions{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}@media(max-width:1000px){.graph-layout{grid-template-columns:1fr}}
"""

SCRIPT = r"""
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('graph-data').textContent);
  const $ = id => document.getElementById(id);
  const nodes = new Map(data.nodes.map(n => [n.id,n]));
  const edges = new Map(data.edges.map(e => [e.id,e]));
  let focus = '', expanded = new Set(), scale = 1;
  const color = {calls:'#176f60',imports:'#4265ad',contains:'#957332'};
  function text(tag, value, parent) {const el=document.createElement(tag);el.textContent=value;parent.append(el);return el;}
  function svg(tag, attrs, parent) {
    const el=document.createElementNS('http:'+'//www.w3.org/2000/svg',tag);
    for(const [key,value] of Object.entries(attrs))el.setAttribute(key,String(value));
    parent.append(el);return el;
  }
  const label = n => n.type==='file'?n.file:n.qualified_name+' · '+n.file;
  function jump(id, title, parent) {
    const a=text('a',title,parent);a.href='#'+id;
    a.addEventListener('click',()=>{let el=$(id);while(el){if(el.tagName==='DETAILS')el.open=true;el=el.parentElement;}});
  }
  function evidence(ids) {
    const detail=$('graph-detail');detail.replaceChildren();
    text('h3','관계 근거 '+ids.length+'개',detail);
    const list=text('ul','',detail);
    for(const id of ids){const e=edges.get(id),r=e.evidence.range,li=text('li','',list);
      text('p',e.type+' · '+(e.expression||'소속')+' · '+(e.resolution_status||'구조'),li);
      jump(id,e.evidence.file+':'+r.start_line+':'+r.start_col,li);
    }
  }
  function describe(id){
    const n=nodes.get(id),detail=$('graph-detail');detail.replaceChildren();
    text('h3',label(n),detail);jump(id,'보고서 코드 상세 보기',detail);
    if(n.docstring)text('p',n.docstring,detail);
    const actions=text('div','',detail);actions.className='graph-actions';
    const select=text('button','이 노드를 중심으로',actions);select.onclick=()=>choose(id);
    const expand=text('button','이 노드 주변 확장',actions);expand.onclick=()=>{expanded.add(id);draw();};
    if(n.type==='file'){
      const b=text('button','파일 안의 정의 펼치기',actions);b.onclick=()=>{$('graph-level').value='symbol';populate(id);};
    }
    const pending=data.edges.filter(e=>!e.target && (e.source===id || (n.type==='file' && nodes.get(e.source).file===n.file)));
    text('p','대상이 없는 관계 '+pending.length+'개 (가상 노드를 만들지 않음)',detail);
    const list=text('ul','',detail);
    for(const e of pending){const li=text('li',e.resolution_status+' · '+e.expression+' · '+(e.reason||e.external_name||e.builtin_name||''),list);jump(e.id,' 근거',li);}
  }
  function choose(id){focus=id;expanded=new Set([id]);$('graph-node').value=id;draw();describe(id);}
  function populate(preferred){
    const query=$('graph-search').value.toLocaleLowerCase(),level=$('graph-level').value;
    const candidates=data.nodes.filter(n=>(level==='symbol'||n.type==='file') && (label(n)+' '+(n.docstring||'')).toLocaleLowerCase().includes(query));
    const select=$('graph-node');select.replaceChildren();
    for(const n of candidates){const option=text('option',label(n),select);option.value=n.id;}
    const id=candidates.some(n=>n.id===preferred)?preferred:candidates[0]?.id;
    if(id)choose(id);else{focus='';$('graph-svg').replaceChildren();$('graph-detail').replaceChildren();$('graph-status').textContent='일치하는 코드 요소가 없습니다.';}
  }
  function draw(){
    if(!focus)return;
    const kinds=new Set(Array.from(document.querySelectorAll('[data-graph-kind]:checked')).map(e=>e.value));
    const level=$('graph-level').value,direction=$('graph-direction').value;
    const relations=(level==='file'?data.file_edges:data.symbol_edges).filter(e=>kinds.has(e.type));
    const wanted=new Set([focus]),eligible=[];
    for(const e of relations){
      if((direction!=='in'&&expanded.has(e.source))||(direction!=='out'&&expanded.has(e.target))){eligible.push(e);wanted.add(e.source);wanted.add(e.target);}
    }
    // Deterministic caps; all omitted elements are counted instead of silently dropped.
    const shown=Array.from(wanted).slice(0,40),visible=new Set(shown);
    const drawable=eligible.filter(e=>visible.has(e.source)&&visible.has(e.target)).slice(0,100);
    $('graph-status').textContent=`노드 ${shown.length}/${wanted.size} · 관계 묶음 ${drawable.length}/${eligible.length} · 생략 ${wanted.size-shown.length}개 노드 / ${eligible.length-drawable.length}개 관계 · 초기 1단계, 최대 노드 40 / 관계 100. 화살표는 원래 방향입니다.`;
    const canvas=$('graph-svg');canvas.replaceChildren();
    const height=Math.max(400,Math.ceil((shown.length-1)/2)*85+90),width=1000;
    canvas.setAttribute('viewBox',`0 0 ${width} ${height}`);canvas.style.width=(scale*100)+'%';
    const defs=svg('defs',{},canvas);
    for(const kind of Object.keys(color)){const marker=svg('marker',{id:'graph-arrow-'+kind,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto-start-reverse'},defs);svg('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:color[kind]},marker);}
    const positions=new Map([[focus,{x:500,y:height/2}]]);
    shown.filter(id=>id!==focus).forEach((id,i)=>positions.set(id,{x:i%2?815:185,y:55+Math.floor(i/2)*85}));
    drawable.forEach((e,i)=>{
      const a=positions.get(e.source),b=positions.get(e.target),same=e.source===e.target;
      const path=same?`M ${a.x-35} ${a.y-22} C ${a.x-100} ${a.y-90},${a.x+100} ${a.y-90},${a.x+35} ${a.y-22}`:
        `M ${a.x} ${a.y} Q ${(a.x+b.x)/2} ${(a.y+b.y)/2+24+(i%3)*12} ${b.x+(a.x>b.x?130:-130)} ${b.y}`;
      const g=svg('g',{class:'graph-edge',tabindex:0,role:'button','aria-label':e.type+' '+label(nodes.get(e.source))+' → '+label(nodes.get(e.target))},canvas);
      svg('path',{d:path,stroke:color[e.type],fill:'none','stroke-width':2,'stroke-dasharray':e.type==='contains'?'5 4':'none','marker-end':'url(#graph-arrow-'+e.type+')'},g);
      const t=svg('text',{x:same?a.x:(a.x+b.x)/2,y:same?a.y-62:(a.y+b.y)/2+12+(i%3)*12,fill:color[e.type],'font-size':12},g);t.textContent=e.type+' ×'+e.edge_ids.length;
      g.onclick=()=>evidence(e.edge_ids);g.onkeydown=event=>{if(event.key==='Enter')evidence(e.edge_ids);};
    });
    for(const id of shown){const n=nodes.get(id),p=positions.get(id),g=svg('g',{class:'graph-node',tabindex:0,role:'button','aria-label':label(n)},canvas);
      g.setAttribute('data-node-id',id);
      svg('rect',{x:p.x-130,y:p.y-23,width:260,height:46,rx:8,fill:id===focus?'#d5eee3':'white',stroke:'#6b9f8d'},g);
      const title=svg('title',{},g);title.textContent=label(n);
      const t=svg('text',{x:p.x,y:p.y+4,'text-anchor':'middle','font-size':12,fill:'#17312e'},g);const name=n.type==='file'?n.file:n.qualified_name;t.textContent=name.length>32?name.slice(0,29)+'…':name;
      g.onclick=()=>describe(id);g.ondblclick=()=>choose(id);g.onkeydown=e=>{if(e.key==='Enter')describe(id);};
    }
  }
  $('graph-search').oninput=()=>populate(focus);
  $('graph-level').onchange=()=>populate();
  $('graph-node').onchange=e=>choose(e.target.value);
  $('graph-direction').onchange=draw;
  document.querySelectorAll('[data-graph-kind]').forEach(e=>e.onchange=draw);
  $('graph-reset').onclick=()=>{expanded=new Set([focus]);scale=1;draw();};
  $('graph-expand').onclick=()=>{for(const el of $('graph-svg').querySelectorAll('.graph-node'))expanded.add(el.getAttribute('data-node-id'));draw();};
  $('graph-zoom-in').onclick=()=>{scale=Math.min(3,scale+.25);draw();};
  $('graph-zoom-out').onclick=()=>{scale=Math.max(.75,scale-.25);draw();};
  populate();
})();
"""


def script_hash():
    return base64.b64encode(hashlib.sha256(SCRIPT.encode("utf-8")).digest()).decode("ascii")


def render_graph(result):
    payload = json.dumps(graph_data(result), ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return '''<section id="graph"><h2>관계 그래프</h2>
<p class="muted">파일을 선택하고 주변 관계를 탐색하세요. 노드 선택 후 정의를 펼치거나 주변을 확장할 수 있습니다. 관계 선을 선택하면 모든 근거 위치를 확인합니다. 실제 실행 순서도가 아닙니다.</p>
<noscript>그래프는 JavaScript가 필요합니다. 아래 파일 관계와 코드 상세는 JavaScript 없이도 읽을 수 있습니다.</noscript>
<div class="graph-controls">
<label>이름·경로·docstring 검색<input id="graph-search" type="search" placeholder="함수 또는 파일 이름"></label>
<label>표시 단위<select id="graph-level"><option value="file">파일</option><option value="symbol">파일·정의</option></select></label>
<label>중심 요소<select id="graph-node" aria-label="중심 요소"></select></label>
<label>방향<select id="graph-direction"><option value="both">양방향</option><option value="out">나가는 관계</option><option value="in">들어오는 관계</option></select></label>
<label><input type="checkbox" data-graph-kind value="calls" checked>calls · 호출</label>
<label><input type="checkbox" data-graph-kind value="imports" checked>imports · 가져오기</label>
<label><input type="checkbox" data-graph-kind value="contains" checked>contains · 소속</label>
</div><div class="graph-actions"><button id="graph-expand">표시된 노드 주변 확장</button><button id="graph-reset">1단계로 초기화</button><button id="graph-zoom-in" aria-label="확대">확대 +</button><button id="graph-zoom-out" aria-label="축소">축소 −</button></div>
<p id="graph-status" class="meta" role="status"></p><div class="graph-layout"><div class="graph-canvas"><svg id="graph-svg" role="group" aria-label="정적 코드 관계 그래프"></svg></div><div id="graph-detail" class="graph-detail" aria-live="polite"></div></div>
</section>''' + '<script type="application/json" id="graph-data">' + payload + '</script>' + '<script>' + SCRIPT + '</script>'

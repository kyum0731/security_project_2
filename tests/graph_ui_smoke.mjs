// Optional Node smoke check using a minimal DOM. This is not browser visual QA.
import assert from 'node:assert/strict';

class Element {
  constructor(tag) {this.tagName=tag.toUpperCase();this.children=[];this.attrs={};this.style={};this.value='';this.textContent='';}
  append(el) {this.children.push(el);el.parentElement=this;}
  replaceChildren(...els) {this.children=[];els.forEach(el=>this.append(el));}
  setAttribute(key,value) {this.attrs[key]=value;}
  getAttribute(key) {return this.attrs[key];}
  addEventListener(event,handler) {this['on'+event]=handler;}
  querySelectorAll(selector) {return this.children.flatMap(el=>[(el.attrs.class===selector.slice(1)?el:null),...el.querySelectorAll(selector)]).filter(Boolean);}
}
const ids = new Map(['graph-data','graph-search','graph-level','graph-node','graph-direction','graph-svg','graph-status','graph-detail','graph-reset','graph-expand','graph-zoom-in','graph-zoom-out'].map(id=>[id,new Element('div')]));
const kinds=['calls','imports','contains'].map(value=>Object.assign(new Element('input'),{value,checked:true}));
ids.get('graph-level').value='file';ids.get('graph-direction').value='both';
const range={start_line:1,start_col:0,end_line:1,end_col:1};
const nodes=[{id:'a',type:'file',file:'a.py',name:'a.py',qualified_name:''},{id:'b',type:'file',file:'b.py',name:'b.py',qualified_name:''},{id:'c',type:'function',file:'b.py',name:'run',qualified_name:'run'}];
const edges=[{id:'e1',source:'a',target:'c',type:'calls',expression:'run()',resolution_status:'resolved',evidence:{file:'a.py',range}},{id:'e2',source:'a',target:null,type:'calls',expression:'unknown()',resolution_status:'unresolved',evidence:{file:'a.py',range}},{id:'e3',source:'b',target:'c',type:'contains',evidence:{file:'b.py',range}}];
ids.get('graph-data').textContent=JSON.stringify({nodes,edges,file_edges:[{source:'a',target:'b',type:'calls',edge_ids:['e1']}],symbol_edges:edges.filter(e=>e.target).map(e=>({...e,edge_ids:[e.id]}))});
globalThis.document={getElementById:id=>ids.get(id),createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),querySelectorAll:selector=>selector.endsWith(':checked')?kinds.filter(k=>k.checked):kinds};
await import('../build/graph-script.mjs');
const status=()=>ids.get('graph-status').textContent;
assert.match(status(),/노드 2\/2/);
assert.equal(ids.get('graph-svg').querySelectorAll('.graph-edge').length,1);
ids.get('graph-svg').querySelectorAll('.graph-edge')[0].onclick();
assert.equal(ids.get('graph-detail').children[0].textContent,'관계 근거 1개');
ids.get('graph-direction').value='in';ids.get('graph-direction').onchange();
assert.match(status(),/노드 1\/1/);
ids.get('graph-direction').value='both';ids.get('graph-direction').onchange();
kinds[0].checked=false;kinds[0].onchange();assert.match(status(),/관계 묶음 0\/0/);
kinds[0].checked=true;kinds[0].onchange();
ids.get('graph-level').value='symbol';ids.get('graph-level').onchange();
ids.get('graph-expand').onclick();assert.match(status(),/노드 3\/3/);
ids.get('graph-reset').onclick();assert.match(status(),/노드 2\/2/);
ids.get('graph-search').value='no-match';ids.get('graph-search').oninput();assert.match(status(),/없습니다/);
ids.get('graph-search').value='run';ids.get('graph-search').oninput();assert.match(status(),/노드 3\/3/);
ids.get('graph-zoom-in').onclick();assert.equal(ids.get('graph-svg').style.width,'125%');
ids.get('graph-level').value='file';ids.get('graph-direction').value='both';ids.get('graph-search').value='';
const denseNodes=Array.from({length:46},(_,i)=>({id:'n'+i,type:'file',file:i+'.py',qualified_name:'',name:i+'.py'}));
const denseEdges=denseNodes.slice(1).flatMap(n=>['calls','imports','contains'].map(type=>({id:n.id+type,source:'n0',target:n.id,type,evidence:{file:'0.py',range},edge_ids:[n.id+type]})));
ids.get('graph-data').textContent=JSON.stringify({nodes:denseNodes,edges:denseEdges,file_edges:denseEdges,symbol_edges:denseEdges});
await import('../build/graph-script-dense.mjs');
assert.match(status(),/노드 40\/46/);assert.match(status(),/관계 묶음 100\/135/);
delete globalThis.document;
console.log('Graph DOM smoke: initial neighborhood, filters, direction, expansion, reset, search, evidence, zoom and caps OK');

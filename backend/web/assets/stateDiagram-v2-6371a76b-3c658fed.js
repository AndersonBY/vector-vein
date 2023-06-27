import{p as Q,d as O,s as X,D as H,a as Z,S as F,b as j,c as I}from"./styles-fa41df25-ba953ec2.js";import{G as tt}from"./layout-75405640.js";import{n as l,h as g,l as x,B as et,o as ot,p as w}from"./EchartsRenderer-7a287037.js";import{r as st}from"./index-a92ac404-52ad4ed0.js";import"./index-bbb581e8.js";import"./TemperatureInput-ce9583ae.js";import"./_plugin-vue_export-helper-c27b6911.js";import"./edges-49ac43a2-4ab4a115.js";import"./createText-3df630b5-cf6d2531.js";import"./index-d0e2ad8e.js";import"./svgDraw-0fcc813d-854bf3b3.js";import"./line-f0938619.js";import"./array-9f3ba611.js";import"./path-53f90ab3.js";const A="rect",C="rectWithTitle",nt="start",ct="end",it="divider",rt="roundedWithTitle",lt="note",at="noteGroup",_="statediagram",dt="state",Et=`${_}-${dt}`,U="transition",St="note",pt="note-edge",Tt=`${U} ${pt}`,_t=`${_}-${St}`,ut="cluster",Dt=`${_}-${ut}`,ft="cluster-alt",bt=`${_}-${ft}`,V="parent",Y="note",ht="state",N="----",At=`${N}${Y}`,M=`${N}${V}`,m="fill:none",W="fill: #333",z="c",q="text",K="normal";let y={},E=0;const yt=function(t){const n=Object.keys(t);for(const e of n)t[e]},gt=function(t,n){l.trace("Extracting classes"),n.db.clear();try{return n.parser.parse(t),n.db.extract(n.db.getRootDocV2()),n.db.getClasses()}catch(e){return e}};function $t(t){return t==null?"":t.classes?t.classes.join(" "):""}function R(t="",n=0,e="",c=N){const i=e!==null&&e.length>0?`${c}${e}`:"";return`${ht}-${t}${i}-${n}`}const h=(t,n,e,c,i,r)=>{const o=e.id,u=$t(c[o]);if(o!=="root"){let p=A;e.start===!0&&(p=nt),e.start===!1&&(p=ct),e.type!==H&&(p=e.type),y[o]||(y[o]={id:o,shape:p,description:w.sanitizeText(o,g()),classes:`${u} ${Et}`});const s=y[o];e.description&&(Array.isArray(s.description)?(s.shape=C,s.description.push(e.description)):s.description.length>0?(s.shape=C,s.description===o?s.description=[e.description]:s.description=[s.description,e.description]):(s.shape=A,s.description=e.description),s.description=w.sanitizeTextOrArray(s.description,g())),s.description.length===1&&s.shape===C&&(s.shape=A),!s.type&&e.doc&&(l.info("Setting cluster for ",o,G(e)),s.type="group",s.dir=G(e),s.shape=e.type===Z?it:rt,s.classes=s.classes+" "+Dt+" "+(r?bt:""));const T={labelStyle:"",shape:s.shape,labelText:s.description,classes:s.classes,style:"",id:o,dir:s.dir,domId:R(o,E),type:s.type,padding:15};if(T.centerLabel=!0,e.note){const a={labelStyle:"",shape:lt,labelText:e.note.text,classes:_t,style:"",id:o+At+"-"+E,domId:R(o,E,Y),type:s.type,padding:15},d={labelStyle:"",shape:at,labelText:e.note.text,classes:s.classes,style:"",id:o+M,domId:R(o,E,V),type:"group",padding:0};E++;const D=o+M;t.setNode(D,d),t.setNode(a.id,a),t.setNode(o,T),t.setParent(o,D),t.setParent(a.id,D);let S=o,f=a.id;e.note.position==="left of"&&(S=a.id,f=o),t.setEdge(S,f,{arrowhead:"none",arrowType:"",style:m,labelStyle:"",classes:Tt,arrowheadStyle:W,labelpos:z,labelType:q,thickness:K})}else t.setNode(o,T)}n&&n.id!=="root"&&(l.trace("Setting node ",o," to be child of its parent ",n.id),t.setParent(o,n.id)),e.doc&&(l.trace("Adding nodes children "),xt(t,e,e.doc,c,i,!r))},xt=(t,n,e,c,i,r)=>{l.trace("items",e),e.forEach(o=>{switch(o.stmt){case j:h(t,n,o,c,i,r);break;case H:h(t,n,o,c,i,r);break;case F:{h(t,n,o.state1,c,i,r),h(t,n,o.state2,c,i,r);const u={id:"edge"+E,arrowhead:"normal",arrowTypeEnd:"arrow_barb",style:m,labelStyle:"",label:w.sanitizeText(o.description,g()),arrowheadStyle:W,labelpos:z,labelType:q,thickness:K,classes:U};t.setEdge(o.state1.id,o.state2.id,u,E),E++}break}})},G=(t,n=I)=>{let e=n;if(t.doc)for(let c=0;c<t.doc.length;c++){const i=t.doc[c];i.stmt==="dir"&&(e=i.value)}return e},Ct=async function(t,n,e,c){l.info("Drawing state diagram (v2)",n),y={},c.db.getDirection();const{securityLevel:i,state:r}=g(),o=r.nodeSpacing||50,u=r.rankSpacing||50;l.info(c.db.getRootDocV2()),c.db.extract(c.db.getRootDocV2()),l.info(c.db.getRootDocV2());const p=c.db.getStates(),s=new tt({multigraph:!0,compound:!0}).setGraph({rankdir:G(c.db.getRootDocV2()),nodesep:o,ranksep:u,marginx:8,marginy:8}).setDefaultEdgeLabel(function(){return{}});h(s,void 0,c.db.getRootDocV2(),p,c.db,!0);let T;i==="sandbox"&&(T=x("#i"+n));const a=i==="sandbox"?x(T.nodes()[0].contentDocument.body):x("body"),d=a.select(`[id="${n}"]`),D=a.select("#"+n+" g");await st(D,s,["barb"],_,n);const S=8;et.insertTitle(d,"statediagramTitleText",r.titleTopMargin,c.db.getDiagramTitle());const f=d.node().getBBox(),L=f.width+S*2,P=f.height+S*2;d.attr("class",_);const k=d.node().getBBox();ot(d,P,L,r.useMaxWidth);const v=`${k.x-S} ${k.y-S} ${L} ${P}`;l.debug(`viewBox ${v}`),d.attr("viewBox",v);const J=document.querySelectorAll('[id="'+n+'"] .edgeLabel .label');for(const $ of J){const B=$.getBBox(),b=document.createElementNS("http://www.w3.org/2000/svg",A);b.setAttribute("rx",0),b.setAttribute("ry",0),b.setAttribute("width",B.width),b.setAttribute("height",B.height),$.insertBefore(b,$.firstChild)}},Rt={setConf:yt,getClasses:gt,draw:Ct},mt={parser:Q,db:O,renderer:Rt,styles:X,init:t=>{t.state||(t.state={}),t.state.arrowMarkerAbsolute=t.arrowMarkerAbsolute,O.clear()}};export{mt as diagram};

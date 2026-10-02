// mindmap.html 의 레이아웃 수식만 떼어 검증 (DOM 없음)
const COLW=210, ROWH=42, NW=176, NH=30, NH2=40, PAD=16;
function layout(TREE){
  let nodes=[], leaf=0;
  (function walk(n, depth){
    n.depth=depth; n.h=n.s?NH2:NH;
    if(n.children && n.children.length){
      n.children.forEach(c=>walk(c, depth+1));
      const f=n.children[0], l=n.children[n.children.length-1];
      n.y=((f.y+f.h/2)+(l.y+l.h/2))/2 - n.h/2;
    } else { n.y=leaf*ROWH; leaf++; }
    n.x=PAD+depth*COLW;
    nodes.push(n);
  })(TREE,0);
  const maxDepth=nodes.reduce((m,n)=>Math.max(m,n.depth),0);
  return {nodes, leaf, W:PAD*2+maxDepth*COLW+NW, H:leaf*ROWH+PAD*2};
}
const T={label:'PRD', s:'x', children:[
  {label:'R-01', s:'r1', children:[{label:'f1', children:[{label:'d1'},{label:'d2'}]},{label:'f2'}]},
  {label:'R-02', children:[{label:'f3'}]},
]};
const {nodes,leaf,W,H}=layout(T);
const c=(n)=>n.y+n.h/2;                       // 세로 중심
const by=Object.fromEntries(nodes.map(n=>[n.label,n]));

let fail=0; const ok=(m,v)=>{ console.log((v?'ok   ':'FAIL ')+m); if(!v)fail++; };
ok('잎 4개', leaf===4);
ok('NaN 없음', nodes.every(n=>Number.isFinite(n.x)&&Number.isFinite(n.y)));
ok('잎 y 가 서로 다름', new Set(nodes.filter(n=>!n.children).map(n=>n.y)).size===4);
ok('f1 중심 = d1·d2 중심의 평균', Math.abs(c(by.f1)-(c(by.d1)+c(by.d2))/2)<1e-9);
ok('R-01 중심 = f1·f2 중심의 평균', Math.abs(c(by['R-01'])-(c(by.f1)+c(by.f2))/2)<1e-9);
ok('PRD 중심 = R-01·R-02 중심의 평균', Math.abs(c(by.PRD)-(c(by['R-01'])+c(by['R-02']))/2)<1e-9);
ok('모든 노드가 캔버스 안(y)', nodes.every(n=>n.y>=-1e-9 && n.y+n.h<=H-PAD*2+1e-9));
ok('깊이별 x 계단', by.PRD.x<by['R-01'].x && by['R-01'].x<by.f1.x && by.f1.x<by.d1.x);
console.log(`\nW=${W} H=${H} · ${fail?fail+' FAILED':'전부 통과'}`);
process.exit(fail?1:0);

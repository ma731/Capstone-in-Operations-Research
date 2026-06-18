const pptxgen = require("pptxgenjs");
const FIG = "figs/";
const OUT = "";
const C={navy:"00338D",navyD:"002564",cer:"0098E0",cerT:"E6F4FC",white:"FFFFFF",ink:"1A1A1A",muted:"586173",
  line:"C9D2E0",gold:"E8A33D",goldT:"FAF1DF",goldD:"8A5C16",blueT:"EEF3FB"};
const F="Palatino Linotype";
const A={heat:2.17,bar:1.524,tail:1.99,cv:3.45,cop:2.55,map:1.66,sched:4.26,mech:1.72,transfer:2.00,vvc:1.55,canyon:1.62,network:1.507,usmap:1.645,droeq:2.752,landscape:1.57};
const pres=new pptxgen(); pres.defineLayout({name:"A0",width:33.11,height:46.81}); pres.layout="A0";
pres.author="Marco Ortiz Togashi"; pres.title="Carbon DRO capstone poster";
const s=pres.addSlide(); s.background={color:C.white};
const W=33.11,Hh=46.81,M=0.7,UW=W-2*M;
const shd=()=>({type:"outer",color:"AEB7C6",blur:7,offset:2,angle:135,opacity:0.22});
function rect(x,y,w,h,fill,o={}){s.addShape(pres.shapes.RECTANGLE,{x,y,w,h,fill:{color:fill},line:o.line||{type:"none"},...(o.shadow?{shadow:shd()}:{})});}
function oval(x,y,w,h,fill){s.addShape(pres.shapes.OVAL,{x,y,w,h,fill:{color:fill},line:{type:"none"}});}
function kpiGlyph(i,cx,gy,big){const col=big?C.goldD:C.cer;
 if(i==0){oval(cx-0.62,gy-0.09,0.18,0.18,C.navy);oval(cx+0.44,gy-0.09,0.18,0.18,C.navy);s.addShape(pres.shapes.LINE,{x:cx-0.44,y:gy,w:0.88,h:0,line:{color:col,width:3.5}});}
 else if(i==1){s.addShape(pres.shapes.LINE,{x:cx-0.6,y:gy,w:1.2,h:0,line:{color:col,width:4}});}
 else if(i==2){s.addShape(pres.shapes.LINE,{x:cx,y:gy+0.16,w:0,h:-0.34,line:{color:col,width:4.5,endArrowType:"triangle"}});}
 else{s.addShape(pres.shapes.LINE,{x:cx-0.6,y:gy,w:1.2,h:0,line:{color:col,width:4.5,endArrowType:"triangle"}});}}
function imgc(p,x,y,w,h,pd=0){s.addImage({path:p,x:x+pd,y:y+pd,w:w-2*pd,h:h-2*pd,sizing:{type:"contain",w:w-2*pd,h:h-2*pd}});}
function figAsp(p,x,y,w,aspect){const h=w/aspect; imgc(p,x,y,w,h,0.05); return h;}
function figCard(p,x,y,w,aspect){const h=w/aspect; rect(x-0.13,y-0.08,w+0.26,h+0.16,"FBFCFE",{line:{color:"E2E8F1",width:1}}); imgc(p,x,y,w,h,0.05); return h;}
function T(r,x,y,w,h,o={}){s.addText(r,{x,y,w,h,fontFace:F,fontSize:o.fs||22,color:o.color||C.ink,bold:o.bold||false,italic:o.italic||false,align:o.align||"left",valign:o.valign||"top",margin:0,lineSpacingMultiple:o.lsm||1.18,charSpacing:o.cs||0});}
function hr(x,y,w,col){rect(x,y,w,0.045,col||C.cer);}
const B=t=>({text:t,options:{bold:true,color:C.navy}});
const G=t=>({text:t,options:{bold:true,color:C.goldD}});
const CT=t=>({text:t,options:{italic:true,color:C.cer}});
const N=t=>({text:t});
function cap(runs,x,y,w){s.addText(runs,{x,y,w,h:0.95,fontFace:F,fontSize:17,color:C.muted,italic:true,align:"left",valign:"top",margin:0,lineSpacingMultiple:1.05});return 0.95;}
function scap(runs,x,y,w){s.addText(runs,{x,y,w,h:0.6,fontFace:F,fontSize:16.5,color:C.muted,italic:true,align:"left",valign:"top",margin:0,lineSpacingMultiple:1.02});return 0.6;}

// ================= BANNER =================
const tbY=0.7,tbH=4.3; rect(M,tbY,UW,tbH,C.navy); rect(M,tbY+tbH,UW,0.16,C.gold);
imgc(FIG+"ie_logo_white.png",M+0.55,tbY+0.55,4.4,3.2);
// thin vertical rules separating the three banner zones
rect(M+5.0,tbY+0.55,0.02,tbH-1.1,"335FA4");
rect(W-M-5.35,tbY+0.55,0.02,tbH-1.1,"335FA4");
T("DATA & TOOLS",W-M-4.75,tbY+0.42,4.7,0.4,{fs:16,bold:true,color:C.gold,cs:2,align:"left"});
imgc(FIG+"em_bolt_white.png",W-M-4.8,tbY+0.92,0.95,1.32);
T("Electricity Maps",W-M-3.7,tbY+1.08,3.65,0.7,{fs:27,bold:true,color:C.white,align:"left",valign:"middle"});
T("Real-time grid carbon, 2021 to 2025",W-M-4.75,tbY+2.12,4.7,0.45,{fs:16,color:"BFD3EA",align:"left"});
T([{text:"Solved with ",options:{color:"BFD3EA"}},{text:"CVXPY · CLARABEL · HiGHS",options:{bold:true,color:C.white}}],W-M-4.75,tbY+2.62,4.7,0.45,{fs:15.5,align:"left"});
const tx=M+5.35,tw=(W-M-5.35)-0.35-tx;
T("CARBON-AWARE DATA-CENTER SCHEDULING",tx,tbY+0.42,tw,0.42,{fs:16.5,bold:true,color:C.gold,align:"center",cs:3});
T("The Price of Sophistication: When Do Spatial and\nRobust Models Pay in Carbon-Aware Scheduling?",tx,tbY+0.88,tw,2.0,{fs:47,bold:true,color:C.white,align:"center",valign:"middle",lsm:1.0});
T("A day-ahead migration scheduler and a complexity-value decision rule",tx,tbY+2.92,tw,0.55,{fs:24,bold:true,italic:true,color:"E3EEFA",align:"center"});
hr(tx+tw/2-1.6,tbY+3.5,3.2,C.gold);
T([{text:"Marco Ortiz Togashi",options:{bold:true}},{text:"     |     Supervisor: Prof. Bissan Ghaddar     |     IE University, Master in Business Analytics & Data Science"}],tx,tbY+3.62,tw,0.55,{fs:20,color:C.white,align:"center"});

// ================= METHOD FLOW =================
const mfY=tbY+tbH+0.5,mfH=1.55;
["Day-ahead\nforecast","Migration\nscheduler","Price each\nmodeling layer","Decision\nrule"].forEach((t,i)=>{
  const sgap=1.1, sw=(UW-3*sgap)/4, x=M+i*(sw+sgap);
  rect(x,mfY,sw,mfH,C.blueT);
  T(t,x+0.15,mfY,sw-0.3,mfH,{fs:21,bold:true,color:C.navy,align:"center",valign:"middle",lsm:1.05});
  if(i<3){const ax=x+sw+0.12; s.addShape(pres.shapes.LINE,{x:ax,y:mfY+mfH/2,w:sgap-0.24,h:0,line:{color:C.cer,width:5,endArrowType:"triangle"}});}
});

// ================= KPI BAND =================
const khY=mfY+mfH+0.5;
T([N("Active inter-region migration cuts worst-case emissions "),{text:"4.0 to 9.9%",options:{bold:true,color:C.goldD}},N("; added "),{text:"sophistication",options:{bold:true,color:C.navy}},N(" (joint covariance, robustness) does not pay until a severity "),{text:"real grids never reach",options:{bold:true,color:C.navy}},N(".")],M,khY,UW,0.7,{fs:27,bold:true,color:C.ink,align:"center",valign:"middle"});
const kY=khY+0.85, kH=4.4, kg=0.4, tw4=(UW-3*kg)/4;
function tile(i,num,numC,fill,label,kicker,big){const x=M+i*(tw4+kg);
  rect(x,kY,tw4,kH,fill,{shadow:true});
  // accent cap: gold for the lever, cerise for the rest
  rect(x,kY,tw4,big?0.22:0.13,big?C.gold:C.cer);
  // eyebrow label tied to the top of the tile
  T(kicker,x+0.2,kY+0.34,tw4-0.4,0.42,{fs:18,bold:true,color:big?C.goldD:C.cer,align:"center",cs:2.5});
  kpiGlyph(i,x+tw4/2,kY+1.02,big);
  T(num,x+0.1,kY+1.18,tw4-0.2,1.7,{fs:big?72:62,bold:true,color:numC,align:"center",valign:"middle"});
  hr(x+tw4*0.5-0.55,kY+2.86,1.1,big?C.gold:C.line);
  T(label,x+0.25,kY+3.02,tw4-0.5,1.2,{fs:20,bold:big,color:big?C.goldD:C.muted,align:"center",lsm:1.05});}
tile(0,"~0%",C.navy,C.blueT,"value added by joint\ncovariance and copulas","THE SCREEN",false);
tile(1,"M* = 3",C.navy,C.blueT,"severity where robustness\nfinally starts to pay","THE PRICE",false);
tile(2,"0 / 17",C.navy,C.blueT,"real grids that reach the\nrobustness threshold","THE LIMIT",false);
tile(3,"4-10%",C.goldD,C.goldT,"worst-case (CVaR) emissions cut\nby active inter-region migration","THE LEVER",true);

// ================= SIDEBAR + COLUMNS =================
const top=kY+kH+0.6;
const sbW=7.6,gut=0.55,sbX=M,mainX=M+sbW+gut,mainW=W-M-mainX;
const mcGut=0.55,mcW=(mainW-2*mcGut)/3,mcX=[mainX,mainX+mcW+mcGut,mainX+2*(mcW+mcGut)];
const colBot=32.6;
function sideHead(y,kicker,head){T(kicker,sbX,y,sbW,0.46,{fs:19,bold:true,color:C.goldD,cs:2.5});hr(sbX,y+0.5,sbW,C.gold);T(head,sbX,y+0.64,sbW,0.8,{fs:22,bold:true,color:C.navy,lsm:1.02});return y+1.42;}
let cy=sideHead(top,"BACKGROUND","The promise");
T([N("Modern compute is "),B("flexible"),N(": training and batch jobs shift in time and across data-center sites, so deferring work to "),B("cleaner hours and regions"),N(" lowers operational carbon. Across 2021 to 2025 neighbouring grids move strongly together, so spatial structure looks like free signal a robust scheduler could turn into savings. "),{text:"Question: can measured spatial correlation actually lower out-of-sample carbon?",options:{bold:true,color:C.navy}}],sbX,cy,sbW,2.5,{fs:18,lsm:1.16}); cy+=2.55;
cy=sideHead(cy,"DATA & SETUP","What goes in");
T([{text:"Electricity Maps",options:{bold:true,color:C.navy}},N(" hourly carbon intensity, 2021 to 2025 ("),{text:"43,824 obs/zone",options:{bold:true,color:C.navy}},N("); train 2021 to 2024, single "),{text:"locked 2025 test",options:{bold:true,color:C.navy}},N(". Three US and Canadian grids spanning weak to strong residual correlation (up to 0.78). Facility: R zones × 24 h, 50 MW cap, "),{text:"80% utilization",options:{bold:true,color:C.navy}},N(", 15 MW/h ramp, deferral window 0 to 7 h, inflexible fraction 30 to 75%.")],sbX,cy,sbW,2.6,{fs:17,lsm:1.14}); cy+=2.65;
cy=sideHead(cy,"METHOD","How it is built");
T([N("A "),B("Mahalanobis Wasserstein DRO"),N(", a second-order cone program in "),B("CVXPY (Clarabel/HiGHS)"),N(", minimizing "),B("CVaR"),N(" of carbon cost ("),CT("Rockafellar and Uryasev 2000"),N("):")],sbX,cy,sbW,1.5,{fs:17,lsm:1.16}); cy+=1.5;
cy+=figAsp(FIG+"dro_equation.png",sbX,cy,sbW,A.droeq)+0.12;
T([N("Cross-region value enters "),{text:"only through the off-diagonal blocks of Σ",options:{bold:true,color:C.navy}},N("; the pre-registered "),B("shuffled-marginals test"),N(" zeroes exactly those blocks. We add copula and tail checks, mean ablations, and walk-forward validation to 2025.")],sbX,cy,sbW,1.85,{fs:17,lsm:1.15}); cy+=1.9;
cy=sideHead(cy,"RIGOR","Why you can trust a null");
[["194","unit tests, CI on every push"],["27","cells where TOST confirms a null effect"],["1","mean-dominance theorem bounding the gap"]].forEach((d,i)=>{const ry=cy+i*0.82;
  if(i>0) rect(sbX,ry-0.04,sbW,0.012,C.line);
  T(d[0],sbX+0.02,ry,1.5,0.78,{fs:33,bold:true,color:C.cer,align:"left",valign:"middle"});
  T(d[1],sbX+1.65,ry,sbW-1.65,0.78,{fs:16,bold:true,color:C.navy,align:"left",valign:"middle",lsm:1.02});});

function colHead(x,kicker,head){
  // step-number chip in gold, then the screen/test/mechanism kicker
  const parts=kicker.split("   ");
  T([{text:parts[0]+"   ",options:{bold:true,color:C.goldD}},{text:parts[1]||"",options:{bold:true,color:C.cer}}],x,top,mcW,0.5,{fs:22,cs:2});
  T(head,x,top+0.56,mcW,1.75,{fs:33,bold:true,color:C.navy,lsm:1.02});
  hr(x,top+2.5,mcW,C.gold);}
// shared modular grid: header row, intro row, common first-figure top, bottom box at colBot
const introY=top+2.78, figTop=top+5.15;
// COL 1 - THE LEAD
let bx=mcX[0]; colHead(bx,"STEP 01   THE PREMISE","The spatial signal is real, but does it pay?");
T([N("Across 2021 to 2025, de-seasonalized carbon intensity in neighbouring zones moves together. Residual cross-region correlation reaches "),B("0.78"),N(" in the Western US and 0.73 in the Eastern interconnection. If spatial structure can ever sharpen a robust schedule, this is the regime where it should.")],bx,introY,mcW,2.3,{fs:19,lsm:1.16});
cy=figTop;
cy+=figAsp(FIG+"us_regions_map.png",bx,cy,mcW,A.usmap)+0.08;
cy+=scap([N("Three grids span the US and Canada; the "),{text:"Western US zones form a tightly correlated graph",options:{bold:true,color:C.navy}},N(" (up to 0.78).")],bx,cy,mcW)+0.12;
cy+=figAsp(FIG+"value_vs_corr.png",bx,cy,mcW,A.vvc)+0.1;
cy+=scap([N("But value does not follow: "),{text:"out-of-sample spatial value stays at zero",options:{bold:true,color:C.navy}},N(" as correlation rises from 0.2 to 0.6.")],bx,cy,mcW)+0.16;
{const efH=colBot-cy, hH=0.62, rH=(efH-hH)/3, midX=bx+mcW*0.45;
 rect(bx,cy,mcW,efH,C.white,{line:{color:C.navy,width:1.4}});
 rect(bx,cy,mcW,hH,C.navy);
 T("WE EXPECTED",bx+0.2,cy,mcW*0.45-0.2,hH,{fs:15,bold:true,color:"BFD3EA",valign:"middle",cs:1});
 T("WE FOUND",midX+0.22,cy,mcW*0.55-0.3,hH,{fs:15,bold:true,color:C.white,valign:"middle",cs:1});
 const efRows=[["Correlation sharpens the schedule",[N("Spatial value stays "),{text:"~0%",options:{bold:true,color:C.navy}}]],
   ["Copulas capture the dependence",[N("Even the maximal copula adds nothing")]],
   ["The signal is simply absent",[N("Real, but masked: "),{text:"+1.46%",options:{bold:true,color:C.navy}}]]];
 efRows.forEach((r,i)=>{const ry=cy+hH+i*rH; if(i%2===1) rect(bx,ry,mcW,rH,C.blueT);
   if(i>0) rect(bx,ry,mcW,0.015,C.line);
   rect(midX,ry,0.02,rH,C.line);
   T(r[0],bx+0.2,ry,mcW*0.45-0.32,rH,{fs:15,italic:true,color:C.muted,valign:"middle",lsm:1.0});
   T(r[1],midX+0.22,ry,mcW*0.55-0.38,rH,{fs:16,bold:true,color:C.navy,valign:"middle",lsm:1.0});});}
// COL 2 - THE TEST
bx=mcX[1]; colHead(bx,"STEP 02   THE SCREEN","Does passive sophistication pay? No.");
T([N("We re-fit the scheduler on the full joint covariance and on a block-diagonal version that erases every cross-region term, then compare out-of-sample CVaR of carbon cost. Across grids and horizons the gap "),B("stays at zero"),N(".")],bx,introY,mcW,2.3,{fs:19,lsm:1.16});
cy=figTop;
cy+=figCard(FIG+"finding_bar.png",bx,cy,mcW,A.bar)+0.1;
cy+=scap([N("Real problem versus covariance-only: about zero unless the mean field is removed.")],bx,cy,mcW)+0.12;
cy+=figCard(FIG+"cv_curve.png",bx,cy,mcW,A.cv)+0.1;
cy+=scap([N("Cross-validation picks "),{text:"ε* = 1",options:{bold:true,color:C.navy}},N(": the optimizer truly robustifies, so the null is real.")],bx,cy,mcW)+0.12;
cy+=figCard(FIG+"copula_result.png",bx,cy,mcW,A.cop)+0.1;
cy+=scap([N("Gaussian, Clayton, even the comonotone (maximal) copula: "),{text:"every gain sits at the noise floor.",options:{bold:true,color:C.navy}}],bx,cy,mcW)+0.12;
{const vH=colBot-cy; rect(bx,cy,mcW,vH,C.cerT); rect(bx,cy,0.16,vH,C.cer);
 T([{text:"THE VERDICT   ",options:{bold:true,color:C.navy,cs:1}},{text:"across every estimator and test, the out-of-sample spatial value is statistically indistinguishable from zero.",options:{bold:true,color:C.navy}}],bx+0.34,cy,mcW-0.62,vH,{fs:16.5,valign:"middle",lsm:1.06});}
// COL 3 - THE MECHANISM
bx=mcX[2]; colHead(bx,"STEP 03   THE MECHANISM","Why does it add nothing? The mean field holds it.");
T([N("Mean ablation isolates the cause. Hold the covariance fixed and flatten the mean field, and the same spatial structure now pays "),B("+1.46%"),N(". The signal is real but masked by a dominant mean, not absent.")],bx,introY,mcW,2.3,{fs:19,lsm:1.16});
cy=figTop;
cy+=figAsp(FIG+"carbon_landscape.png",bx,cy,mcW,A.landscape)+0.1;
cy+=scap([N("The "),{text:"dominant mean carbon field",options:{bold:true,color:C.navy}},N(": the schedule follows this terrain; the spatial covariance is a thin ripple on top (≤1.46%).")],bx,cy,mcW)+0.2;
cy+=figAsp(FIG+"certificate_canyon.png",bx,cy,mcW,A.canyon)+0.1;
cy+=scap([N("The mean-dominance theorem caps the gap a-priori at "),{text:"7 to 13% of CVaR",options:{bold:true,color:C.navy}},N("; the realized gap never exceeds 0.23%, about 100x below its own bound.")],bx,cy,mcW)+0.16;
{const rcH=colBot-cy; rect(bx,cy,mcW,rcH,C.blueT); rect(bx,cy,0.16,rcH,C.cer);
 T("THE NULL SURVIVES EVERY CHECK",bx+0.32,cy+0.22,mcW-0.55,0.5,{fs:18,bold:true,color:C.navy,cs:0.5});
 hr(bx+0.32,cy+0.78,mcW-0.64,C.cer);
 const checks=["Ledoit-Wolf covariance shrinkage","Residualization of the mean field","Benjamini-Hochberg over 144 cells","Walk-forward validation to 2024","Ramp and utilization sweeps","The full CVaR tail range, 0.80 to 0.99"];
 const c0=cy+0.95, chRow=(rcH-1.1)/checks.length;
 checks.forEach((t,i)=>{const ry=c0+i*chRow;
   s.addText("✓",{x:bx+0.34,y:ry,w:0.5,h:chRow,fontFace:F,fontSize:18,bold:true,color:C.cer,align:"left",valign:"middle",margin:0});
   T([{text:t,options:{bold:true,color:C.navy}}],bx+0.86,ry,mcW-1.1,chRow,{fs:16.5,valign:"middle",lsm:1.0});});}

// ================= SCHEDULE BAND =================
const sbY2=colBot+0.3, schFigW=UW-0.8, schFigH=schFigW/A.sched, sbBH=0.85+schFigH+0.2;
rect(M,sbY2,UW,sbBH,C.white,{line:{color:C.line,width:1},shadow:true}); rect(M,sbY2,UW,0.16,C.gold);
T("THE RESULT, SEEN DIRECTLY",M+0.45,sbY2+0.32,8.2,0.45,{fs:18,bold:true,color:C.goldD,cs:3});
T([N("Each panel is one Western US grid.  Bars: scheduled load.  Line: carbon intensity.  Joint and shuffled plans overlap.")],M+8.6,sbY2+0.28,UW-9.05,0.5,{fs:15,bold:true,color:C.navy,align:"right",valign:"middle"});
imgc(FIG+"schedule_us_west.png",M+0.4,sbY2+0.85,schFigW,schFigH,0.04);

// ================= PAYOFF + RECOMMENDATION + FOOTER =================
const pY=sbY2+sbBH+0.25,pH=2.85;
rect(M,pY,UW,pH,C.goldT,{line:{color:C.gold,width:1.5}}); rect(M,pY,0.18,pH,C.gold);
imgc(FIG+"schematic_transfer.png",M+0.5,pY+0.22,5.9,pH-0.44);
T("THE PAYOFF",M+6.7,pY+0.4,UW-7.0,0.7,{fs:25,bold:true,color:C.goldD,cs:1});
T([N("The value is in physically moving compute toward whichever grid is clean right now. An "),{text:"active inter-region transfer channel",options:{bold:true,color:C.goldD}},N(" cuts 4 to 10 percent of carbon, deterministically. The sophisticated layers (joint covariance, copulas, distributional robustness) add nothing until grid emergencies hit 3x severity, which real grids never reach. Deploy the simple migration scheduler; price robustness only if your grid faces genuine extremes.")],M+6.7,pY+1.2,UW-7.1,pH-1.35,{fs:19,color:C.goldD,lsm:1.16});
const rY=pY+pH+0.25,rH=1.3;
rect(M,rY,UW,rH,C.navyD); rect(M,rY,0.18,rH,C.gold);
const qz=1.18, qx=W-M-qz-0.22, qy=rY+(rH-qz)/2;
rect(qx-0.13,qy-0.13,qz+0.26,qz+0.26,C.white);
imgc(FIG+"repo_qr.png",qx,qy,qz,qz,0);
T("REPOSITORY\nDATA  ·  THESIS",qx-2.15,rY,1.9,rH,{fs:14,bold:true,color:C.cer,align:"right",valign:"middle",lsm:1.1,cs:1});
T([{text:"RECOMMENDATION    ",options:{bold:true,color:C.gold,cs:2}},{text:"Deploy the deterministic migration scheduler; skip joint-covariance and copula modeling; price robustness only past a severity real grids never reach.",options:{bold:true,color:C.white}}],M+0.75,rY,UW-5.1,rH,{fs:25,align:"left",valign:"middle"});
T([{text:"Marco Ortiz Togashi   ·   marco.ortiztogashi@student.ie.edu      |      Supervisor: Prof. Bissan Ghaddar      |      IE University, MS in Business Analytics & Data Science      |      Carbon data: Electricity Maps (academic licence)."}],M,rY+rH+0.2,UW,0.45,{fs:18,color:C.muted,align:"center"});
T([{text:"References:  Hall et al. 2024 (carbon-aware DRO);  Mohajerin Esfahani and Kuhn 2018 (Wasserstein DRO);  Rockafellar and Uryasev 2000 (CVaR)."}],M,rY+rH+0.64,UW,0.45,{fs:18,italic:true,color:C.muted,align:"center"});

pres.writeFile({fileName:OUT+"poster_capstone_v24.pptx"}).then(f=>console.log("WROTE",f));
// end-of-file-sentinel

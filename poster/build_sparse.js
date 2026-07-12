const pptxgen=require("pptxgenjs");
const FIG="figs/";
const C={navy:"00338D",navyD:"002564",cer:"0098E0",white:"FFFFFF",ink:"16202E",muted:"586173",line:"C9D2E0",gold:"E8A33D",goldT:"FAF1DF",goldD:"8A5C16",blueT:"EEF3FB",sage:"4A7C59"};
const F="Palatino Linotype";
const pres=new pptxgen(); pres.defineLayout({name:"A0",width:33.11,height:46.81}); pres.layout="A0";
const s=pres.addSlide(); s.background={color:C.white};
const W=33.11,H=46.81,M=1.4,UW=W-2*M;
function rect(x,y,w,h,fill,o={}){s.addShape(pres.shapes.RECTANGLE,{x,y,w,h,fill:{color:fill},line:o.line||{type:"none"}});}
function imgc(p,x,y,w,h){s.addImage({path:p,x,y,w,h,sizing:{type:"contain",w,h}});}
function T(r,x,y,w,h,o={}){s.addText(r,{x,y,w,h,fontFace:F,fontSize:o.fs||24,color:o.color||C.ink,bold:o.bold||false,italic:o.italic||false,align:o.align||"left",valign:o.valign||"top",margin:0,lineSpacingMultiple:o.lsm||1.08,charSpacing:o.cs||0});}
function hr(x,y,w,col){rect(x,y,w,0.05,col||C.gold);}
const N=t=>({text:t});
const G=t=>({text:t,options:{bold:true,color:C.goldD}});

// ===== TOP BAND =====
const tbH=3.5; rect(0,0,W,tbH,C.navy); rect(0,tbH,W,0.18,C.gold);
imgc(FIG+"ie_logo_white.png",M,0.55,3.6,2.4);
T("The Price of Sophistication",M+4.3,0.5,UW-12,1.4,{fs:40,bold:true,color:C.white,valign:"middle"});
T("When does extra modelling actually pay in carbon-aware data-center scheduling?",M+4.3,1.95,UW-12,0.9,{fs:21,italic:true,color:"DCE9F7",valign:"middle"});
T([{text:"Marco Ortiz Togashi",options:{bold:true}},{text:"\n Supervisor: Prof. Bissan Ghaddar  ·  IE University"}],W-M-8.5,0.8,8.5,2.0,{fs:18,color:"DCE9F7",align:"right",valign:"middle",lsm:1.2});

// ===== HERO TAKEAWAY =====
T("Just move the compute to the cleanest grid.",M,9.0,UW,2.4,{fs:64,bold:true,color:C.navy,align:"center",valign:"middle"});
T([N("That alone cuts worst-case carbon "),G("4 to 10%"),N("  "),G("(18,000 to 46,000 tonnes CO2 a year).")],M,12.0,UW,1.6,{fs:38,color:C.ink,align:"center",valign:"middle"});
T("Modelling how the grids correlate, on top of that, adds nothing.",M,14.0,UW,1.3,{fs:33,italic:true,color:C.muted,align:"center",valign:"middle"});

// ===== HERO FIGURE (the result, big) =====
const fw=20.5, fh=fw/1.448, fx=(W-fw)/2, fyTop=16.6;
rect(fx-0.25,fyTop-0.2,fw+0.5,fh+0.4,"FBFCFE",{line:{color:"E2E8F1",width:1.2}});
imgc(FIG+"lever_bar_plain.png",fx,fyTop,fw,fh);
T("Out-of-sample worst-case carbon cut by active transfer, on three real grids.",M,fyTop+fh+0.25,UW,0.7,{fs:20,italic:true,color:C.muted,align:"center"});

// ===== THREE SECONDARY FINDINGS =====
const sy=fyTop+fh+1.5, gap=1.0, cw=(UW-2*gap)/3, ch=3.4;
[["about 0%","extra benefit from correlation\nand copula models, so keep it simple"],
 ["M* = 3","how extreme an emergency must be\nbefore robustness is worth it"],
 ["0 of 17","real grids that ever get that\nextreme, so robustness stays on the shelf"]].forEach((d,i)=>{
  const x=M+i*(cw+gap);
  rect(x,sy,cw,ch,C.blueT); rect(x,sy,cw,0.16,C.cer);
  T(d[0],x,sy+0.55,cw,1.5,{fs:52,bold:true,color:C.navy,align:"center",valign:"middle"});
  T(d[1],x+0.35,sy+2.15,cw-0.7,1.1,{fs:21,color:C.muted,align:"center",lsm:1.1});
});

// ===== BOTTOM: practitioner takeaway + QR =====
const rY=H-3.5, rH=2.2;
rect(M,rY,UW,rH,C.goldT,{line:{color:C.gold,width:1.6}}); rect(M,rY,0.22,rH,C.gold);
T("THE BOTTOM LINE",M+0.7,rY+0.35,UW-6.5,0.6,{fs:21,bold:true,color:C.goldD,cs:1.5});
T("Ship the simple migration scheduler now. Skip the joint-covariance and copula modelling. Turn robustness on only if conditions get worse than any real grid has seen.",M+0.7,rY+1.02,UW-6.5,1.0,{fs:25,bold:true,color:C.goldD,lsm:1.1});
const qz=1.7, qx=W-M-qz-0.55, qy=rY+(rH-qz)/2;
rect(qx-0.16,qy-0.16,qz+0.32,qz+0.32,C.white); imgc(FIG+"repo_qr.png",qx,qy,qz,qz);
T("code · data · thesis",qx-0.2,qy+qz+0.04,qz+0.4,0.4,{fs:13,bold:true,color:C.goldD,align:"center"});

pres.writeFile({fileName:"poster_capstone_sparse.pptx"}).then(f=>console.log("WROTE",f));

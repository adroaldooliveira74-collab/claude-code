// Servidor OPCIONAL de ativação online — UrbanClin / Perito·Laudo
// Valida licenças, limita aparelhos por código (anti-compartilhamento) e permite revogar.
// NÃO guarda a chave privada: só a PÚBLICA (verifica). A emissão continua offline no gerador.
// Rodar: ADMIN=suasenha node server/licenca-online.js   (porta padrão 8790)
// Hospede em qualquer VPS/serviço Node e aponte o app com window.VP_ONLINE_URL="https://seu-servidor".
const http=require("http"), fs=require("fs"), path=require("path");
const nacl=require(path.join(__dirname,"..","vendor","tweetnacl.min.js"));
const PUB="yOlJKVw9frMqK3BOe2OjXbqsEMfT8CBotAeyUT4jrtg="; // mesma chave pública do app
const PORT=+(process.env.PORT||8790);
const ADMIN=process.env.ADMIN||""; // senha para revogar
const MAX=+(process.env.MAX_DEVICES||2); // aparelhos por código
const DB=process.env.DB||path.join(__dirname,"licencas.json");

const enc=new TextEncoder(), dec=new TextDecoder();
const b=s=>Uint8Array.from(Buffer.from(s.replace(/-/g,"+").replace(/_/g,"/"),"base64"));
function verify(token){try{const p=(token||"").trim().split(".");if(p.length!==2)return null;
  if(!nacl.sign.detached.verify(enc.encode(p[0]),b(p[1]),b(PUB)))return null;
  return {code:p[0],pl:JSON.parse(dec.decode(b(p[0])))};}catch(e){return null;}}
const load=()=>{try{return JSON.parse(fs.readFileSync(DB,"utf8"));}catch(e){return {codes:{}};}};
const save=x=>fs.writeFileSync(DB,JSON.stringify(x,null,2));
const today=()=>new Date().toISOString().slice(0,10);
function body(req){return new Promise(r=>{let s="";req.on("data",c=>{s+=c;if(s.length>1e5)req.destroy();});req.on("end",()=>{try{r(JSON.parse(s||"{}"));}catch(e){r({});}});});}
function send(res,code,obj){res.writeHead(code,{"Content-Type":"application/json; charset=utf-8","Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"Content-Type, x-admin","Access-Control-Allow-Methods":"GET,POST,OPTIONS"});res.end(JSON.stringify(obj));}

const server=http.createServer(async(req,res)=>{
  if(req.method==="OPTIONS")return send(res,204,{});
  const u=new URL(req.url,"http://x");
  if(u.pathname==="/ping")return send(res,200,{ok:true,app:"licenca-online",max:MAX});
  if(u.pathname==="/validar"&&req.method==="POST"){
    const d=await body(req); const v=verify(d.token);
    if(!v)return send(res,200,{ok:false,erro:"assinatura inválida"});
    if(today()>v.pl.exp)return send(res,200,{ok:false,erro:"licença vencida",exp:v.pl.exp});
    const db=load(); const rec=db.codes[v.code]||(db.codes[v.code]={devices:[],revoked:false,nome:v.pl.n,exp:v.pl.exp});
    if(rec.revoked)return send(res,200,{ok:false,erro:"licença revogada"});
    const dev=(d.device||"").slice(0,80)||"desconhecido";
    if(rec.devices.indexOf(dev)<0){
      if(rec.devices.length>=MAX)return send(res,200,{ok:false,erro:"limite de "+MAX+" aparelho(s) atingido para este código"});
      rec.devices.push(dev); rec.updated=Date.now(); save(db);
    }
    return send(res,200,{ok:true,nome:v.pl.n,exp:v.pl.exp,aparelhos:rec.devices.length,max:MAX});
  }
  if(u.pathname==="/revogar"&&req.method==="POST"){
    if(!ADMIN||req.headers["x-admin"]!==ADMIN)return send(res,401,{ok:false,erro:"admin"});
    const d=await body(req); const v=verify(d.token); if(!v)return send(res,200,{ok:false,erro:"token inválido"});
    const db=load(); const rec=db.codes[v.code]||(db.codes[v.code]={devices:[],nome:v.pl.n,exp:v.pl.exp}); rec.revoked=!(d.liberar); save(db);
    return send(res,200,{ok:true,revogada:rec.revoked});
  }
  if(u.pathname==="/status"&&req.method==="POST"){
    if(!ADMIN||req.headers["x-admin"]!==ADMIN)return send(res,401,{ok:false,erro:"admin"});
    return send(res,200,{codes:load().codes});
  }
  send(res,404,{ok:false,erro:"rota"});
});
server.listen(PORT,()=>console.log("[licenca-online] http://0.0.0.0:"+PORT+"  max aparelhos="+MAX+(ADMIN?"":"  (defina ADMIN para revogar)")));
module.exports={verify};

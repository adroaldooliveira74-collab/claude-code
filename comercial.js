/* UrbanClin · Camada comercial — white-label (marca/cores) + licença (12 meses / modo consulta)
   Carregado por index.html, assistencia.html, painel.html e admin.html.
   A CHAVE PÚBLICA abaixo só verifica licenças; a chave privada (que assina) fica apenas com o vendedor. */
(function(){
  "use strict";
  var PUB = "yOlJKVw9frMqK3BOe2OjXbqsEMfT8CBotAeyUT4jrtg="; // chave pública de verificação
  var LS_BRAND="vp_brand", LS_LIC="vp_lic", LS_SEEN="vp_seen";

  // ---------- util ----------
  function lsGet(k){try{return localStorage.getItem(k);}catch(e){return null;}}
  function lsSet(k,v){try{localStorage.setItem(k,v);}catch(e){}}
  function b2u(s){s=s.replace(/-/g,"+").replace(/_/g,"/");while(s.length%4)s+="=";var bin=atob(s);var u=new Uint8Array(bin.length);for(var i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);return u;}
  var enc=new TextEncoder();
  function today(){return new Date().toISOString().slice(0,10);}

  // ---------- MARCA (white-label) ----------
  var DEF={
    empresa:{nome:"UrbanClin — Medicina e Segurança do Trabalho",cidade:"Perobal",uf:"PR",abrangencia:"Atendimento em todo o Estado do Paraná",tel:"(47) 99167-1874",email:"a.marques_74@live.com"},
    profissional:{nome:"",formacao:"Engenheiro de Segurança do Trabalho",registro:""},
    cores:{principal:"#007a36",secundaria:"#f59c00"},
    logo:"",logoFooter:""
  };
  function loadBrand(){var b={};try{b=JSON.parse(lsGet(LS_BRAND)||"{}");}catch(e){}
    return {
      empresa:Object.assign({},DEF.empresa,b.empresa||{}),
      profissional:Object.assign({},DEF.profissional,b.profissional||{}),
      cores:Object.assign({},DEF.cores,b.cores||{}),
      logo:b.logo||"",logoFooter:b.logoFooter||b.logo||""
    };
  }
  function rodapeLinhas(b){var e=b.empresa;return [
    e.nome,
    (e.cidade?e.cidade+(e.uf?" - "+e.uf:""):"")+(e.abrangencia?" · "+e.abrangencia:""),
    [e.tel,e.email].filter(Boolean).join(" · ")
  ].filter(function(x){return x&&x.trim();});}
  function applyBrand(b){
    try{
      var r=document.documentElement.style;
      if(b.cores.principal){r.setProperty("--accent",b.cores.principal);r.setProperty("--ok",b.cores.principal);}
      if(b.cores.secundaria){r.setProperty("--laranja",b.cores.secundaria);}
      // logos já presentes
      if(b.logo){["#brandLogo","#homeLogo"].forEach(function(s){var el=document.querySelector(s);if(el)el.src=b.logo;});
        document.querySelectorAll("img[data-brandlogo]").forEach(function(el){el.src=b.logo;});}
    }catch(e){}
  }

  // ---------- LICENÇA ----------
  function verify(token){
    try{
      var n=(window.nacl); if(!n) return {ok:false,err:"cripto"};
      var p=token.trim().split("."); if(p.length!==2) return {ok:false,err:"formato"};
      var okSig=n.sign.detached.verify(enc.encode(p[0]), b2u(p[1]), b2u(PUB));
      if(!okSig) return {ok:false,err:"assinatura"};
      var pl=JSON.parse(new TextDecoder().decode(b2u(p[0])));
      return {ok:true,pl:pl};
    }catch(e){return {ok:false,err:String(e&&e.message||e)};}
  }
  function evalLicense(){
    var token=lsGet(LS_LIC)||"";
    var seen=lsGet(LS_SEEN)||""; var hoje=today();
    var res={state:"sem",pl:null,token:token};
    if(token){
      var v=verify(token);
      if(!v.ok){res.state="invalida";}
      else{
        res.pl=v.pl;
        var rollback = seen && hoje < seen;              // relógio atrasado (fraude)
        var expirada = hoje > v.pl.exp;
        res.state = (rollback||expirada) ? "expirada" : "ativa";
      }
    }
    // atualiza "maior data já vista" (anti-rollback) só avança
    if(!seen || hoje>seen) lsSet(LS_SEEN,hoje);
    return res;
  }

  // ---------- MODO CONSULTA (trava de edição/exportação) ----------
  var BLOCK=/baixar|\bpdf\b|word|gerar|montar|atualizar laudo|analisar|✨|importar|enviar ao servidor|📲|liberar|exportar|copiar texto|salvar|novo|\bapk\b/i;
  var ALLOW=/ativar|licen|leitura|\bler\b|fechar|cancelar|ajuda|voltar|anterior|próximo|proximo|início|inicio|processos|tema|abrir|atualizar$/i;
  function lockConsulta(){
    try{
      document.body.classList.add("vp-consulta");
      var css=document.createElement("style");
      css.textContent=".vp-consulta .vp-ro{background:#f3f4f2!important;cursor:not-allowed}#vpBar{position:fixed;left:0;right:0;top:0;z-index:2147483600;background:linear-gradient(90deg,#b3261e,#8a1d17);color:#fff;font-family:Segoe UI,Arial,sans-serif;font-size:13.5px;font-weight:600;padding:9px 16px;display:flex;align-items:center;gap:12px;box-shadow:0 2px 10px rgba(0,0,0,.25)}#vpBar button{background:#fff;color:#8a1d17;border:0;border-radius:7px;padding:6px 12px;font-weight:800;cursor:pointer;font-size:13px}body.vp-consulta{padding-top:40px}";
      document.head.appendChild(css);
      // tornar campos somente leitura
      function ro(){document.querySelectorAll("input,textarea").forEach(function(el){if(el.type!=="file"){el.readOnly=true;el.classList.add("vp-ro");}});document.querySelectorAll("select").forEach(function(el){el.classList.add("vp-ro");el.addEventListener("mousedown",function(e){if(document.body.classList.contains("vp-consulta")){e.preventDefault();toast();}},true);});}
      ro(); setTimeout(ro,1500);
      // interceptar cliques de ação
      document.addEventListener("click",function(e){
        if(!document.body.classList.contains("vp-consulta"))return;
        var t=e.target.closest("button,a.btn,.btn,label.btn"); if(!t)return;
        var txt=(t.textContent||"")+" "+(t.id||"")+" "+(t.className||"");
        if(t.closest(".tab")||/vp-ok/.test(t.className))return;
        if(BLOCK.test(txt) && !ALLOW.test(txt)){e.preventDefault();e.stopImmediatePropagation();toast();}
      },true);
    }catch(e){}
  }
  var _t;
  function toast(){try{var d=document.getElementById("vpToast");if(!d){d=document.createElement("div");d.id="vpToast";d.style.cssText="position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#1d2a1a;color:#fff;padding:11px 18px;border-radius:10px;font:600 13px Segoe UI,Arial;z-index:2147483600;opacity:0;transition:.2s";document.body.appendChild(d);}d.textContent="🔒 Licença expirada — modo consulta. Renove para editar/gerar documentos.";d.style.opacity=1;clearTimeout(_t);_t=setTimeout(function(){d.style.opacity=0;},2600);}catch(e){}}

  function banner(state,pl){
    var bar=document.createElement("div");bar.id="vpBar";
    var msg = state==="sem" ? "Produto sem licença — modo consulta (somente leitura)."
            : state==="invalida" ? "Licença inválida — modo consulta (somente leitura)."
            : "Licença expirada"+(pl&&pl.exp?" em "+pl.exp.split("-").reverse().join("/"):"")+" — modo consulta (somente leitura).";
    bar.innerHTML='<span>🔒 '+msg+'</span>';
    var b=document.createElement("button");b.textContent="Inserir código de liberação (12 meses)";b.className="vp-ok";
    b.onclick=function(){ativar();};
    bar.appendChild(b);
    document.body.insertBefore(bar,document.body.firstChild);
  }
  function ativar(){
    var cur=lsGet(LS_LIC)||"";
    var k=prompt("Cole aqui o CÓDIGO DE LIBERAÇÃO (licença de 12 meses) enviado na compra:",cur);
    if(k===null)return;
    k=k.trim(); if(!k){return;}
    var v=verify(k);
    if(!v.ok){alert("Código inválido. Confira se copiou o texto inteiro, sem espaços faltando.");return;}
    if(today()>v.pl.exp){alert("Este código já está vencido (validade "+v.pl.exp.split("-").reverse().join("/")+"). Adquira um novo código de 12 meses.");return;}
    lsSet(LS_LIC,k);
    alert("✅ Licença ativada para "+(v.pl.n||"—")+"\nVálida até "+v.pl.exp.split("-").reverse().join("/")+".\nO programa será recarregado.");
    location.reload();
  }

  // ---------- init ----------
  // Parte SÍNCRONA (roda já no <head>, antes do script principal usar a logo/cores)
  var brand=loadBrand();
  window.BRAND={logo:brand.logo,logoFooter:brand.logoFooter,cores:brand.cores,empresa:brand.empresa,profissional:brand.profissional,rodape:rodapeLinhas(brand)};
  try{var rs=document.documentElement.style;if(brand.cores.principal){rs.setProperty("--accent",brand.cores.principal);rs.setProperty("--ok",brand.cores.principal);}if(brand.cores.secundaria)rs.setProperty("--laranja",brand.cores.secundaria);}catch(e){}
  var lic=evalLicense();
  var ENFORCE=(window.VP_ENFORCE===true); // só a versão comercial ativa a trava
  window.VP={brand:brand,license:lic,ativar:ativar,verify:verify,enforce:ENFORCE,applyBrand:function(){var b=loadBrand();window.BRAND.rodape=rodapeLinhas(b);applyBrand(b);}};
  window.VP_LOCKED = ENFORCE && (lic.state!=="ativa");
  // Parte que mexe no DOM (logos, banner, trava) — espera o corpo existir
  function dom(){
    applyBrand(brand);
    if(window.VP_SKIP_LOCK||!ENFORCE)return;
    if(window.VP_LOCKED){banner(lic.state,lic.pl);lockConsulta();}
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",dom); else dom();
})();

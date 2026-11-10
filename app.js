const DATA_URL="./data/matches.json";
const $=id=>document.getElementById(id);
const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const timeFmt=new Intl.DateTimeFormat("es-ES",{timeZone:"Europe/Madrid",hour:"2-digit",minute:"2-digit",hour12:false});
const dateFmt=new Intl.DateTimeFormat("es-ES",{timeZone:"Europe/Madrid",weekday:"long",day:"numeric",month:"long"});
function isToday(value,now){if(!value)return false;const d=new Date(value);return !Number.isNaN(d.getTime())&&new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Madrid",year:"numeric",month:"2-digit",day:"2-digit"}).format(d)===new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Madrid",year:"numeric",month:"2-digit",day:"2-digit"}).format(now)}
function render(data){
  const now=new Date();
  $("today").textContent=dateFmt.format(now);
  const matches=(data.matches||[]).filter(m=>isToday(m.start||m.date,now)).sort((a,b)=>new Date(a.start)-new Date(b.start));
  if(!matches.length){$("matches").innerHTML='<div class="empty">No hay eventos programados para hoy.</div>';}
  else $("matches").innerHTML=matches.map(m=>{
    const live=m.status==="in",done=m.status==="post";
    const time=m.start?timeFmt.format(new Date(m.start)):"— —";
    const channel=m.channel||"Canal por confirmar";
    return `<article class="match ${live?"is-live":""}">
      <div class="kickoff">${esc(time)}<small>${live?"EN JUEGO":done?"FINAL":" "}</small></div>
      <div class="match-body">
        <div class="teams">
          <div class="team"><img loading="lazy" src="${esc(m.home_logo)}" alt="" onerror="this.hidden=true"><span class="team-name">${esc(m.home)}</span></div>
          <span class="vs">VS</span>
          <div class="team away"><img loading="lazy" src="${esc(m.away_logo)}" alt="" onerror="this.hidden=true"><span class="team-name">${esc(m.away)}</span></div>
        </div>
        <div class="details"><span class="competition">${esc(m.competition||"")}</span><span class="channel ${m.channel?"":"pending"}">${esc(channel)}</span></div>
      </div>
    </article>`;
  }).join("");
  $("updated").textContent=data.updated_at?"Actualizado "+new Intl.DateTimeFormat("es-ES",{timeZone:"Europe/Madrid",hour:"2-digit",minute:"2-digit"}).format(new Date(data.updated_at)):"";
}
async function load(){
 try{const r=await fetch(DATA_URL+"?v="+Date.now(),{cache:"no-store"});if(!r.ok)throw Error("No se pudo cargar la cartelera");render(await r.json());}
 catch(e){$("matches").innerHTML='<div class="empty">No se ha podido cargar la cartelera.</div>';}
}
load();setInterval(load,5*60*1000);
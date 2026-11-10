const DATA_URL = "./data/matches.json";
const $ = (id) => document.getElementById(id);
const esc = (value="") => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const madridDate = new Intl.DateTimeFormat("es-ES",{timeZone:"Europe/Madrid",weekday:"long",day:"2-digit",month:"long",year:"numeric"});
const madridTime = new Intl.DateTimeFormat("es-ES",{timeZone:"Europe/Madrid",hour:"2-digit",minute:"2-digit",hour12:false});
function dateKey(date){return new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Madrid",year:"numeric",month:"2-digit",day:"2-digit"}).format(date)}
function render(matches,meta={}){
  const now = new Date();
  $("weekday").textContent = madridDate.format(now).split(",")[0].toUpperCase();
  $("date").textContent = madridDate.format(now).split(",").slice(1).join(",").trim().toUpperCase();
  const todays = matches.filter(m => m.date && m.date.slice(0,10) === dateKey(now)).sort((a,b)=>(a.start||"").localeCompare(b.start||""));
  $("match-count").textContent = todays.length;
  $("ticker-text").textContent = todays.length ? `${todays.length} EVENTOS EN CARTELERA · ${todays.filter(m=>m.status==="in").length} EN DIRECTO` : "NO HAY PARTIDOS PROGRAMADOS PARA HOY";
  $("updated").textContent = meta.updated_at ? "Datos: "+new Date(meta.updated_at).toLocaleTimeString("es-ES",{timeZone:"Europe/Madrid",hour:"2-digit",minute:"2-digit"}) : "Datos de ejemplo";
  $("refresh-label").textContent = "REFRESCO CADA 30 MIN";
  if(!todays.length){
    $("matches").innerHTML='<div class="empty"><p>HOY NO HAY EVENTOS EN ESTA SELECCIÓN</p><small>La cartelera se actualizará automáticamente.</small></div>';
    return;
  }
  $("matches").innerHTML = todays.map(m=>{
    const time = m.start ? madridTime.format(new Date(m.start)) : "--:--";
    const live = m.status==="in";
    const channel = m.channel || "Emisión por confirmar";
    return `<article class="match ${m.featured?"featured":""} ${live?"live":""}">
      <div class="time">${esc(time)}<small>${live?"EN DIRECTO":m.status==="post"?"FINALIZADO":"HORA ESPAÑOLA"}</small></div>
      <div class="teams">
        <div class="team"><img loading="lazy" src="${esc(m.home_logo||"")}" alt="" onerror="this.style.visibility='hidden'"><span class="team-name">${esc(m.home)}</span></div>
        <span class="versus">VS</span>
        <div class="team away"><img loading="lazy" src="${esc(m.away_logo||"")}" alt="" onerror="this.style.visibility='hidden'"><span class="team-name">${esc(m.away)}</span></div>
      </div>
      <div class="meta"><div><div class="competition">${esc(m.competition||"DEPORTE")}</div><div class="venue">${esc(m.venue||"Estadio por confirmar")}</div></div><span class="channel ${m.channel?"":"pending"}">${esc(channel)}</span></div>
    </article>`;
  }).join("");
}
async function load(){
  try{
    const response=await fetch(DATA_URL+"?v="+Date.now(),{cache:"no-store"});
    if(!response.ok) throw new Error("HTTP "+response.status);
    const data=await response.json();
    render(data.matches||[],data);
    $("notice").hidden=false;
    $("notice").textContent="Los canales marcados como «por confirmar» no han podido verificarse en la fuente.";
  }catch(error){
    $("matches").innerHTML='<div class="empty"><p>NO SE HA PODIDO CARGAR LA CARTELERA</p><small>Comprueba que el flujo de GitHub Actions haya terminado correctamente.</small></div>';
    $("notice").hidden=false;$("notice").textContent=error.message;
  }
}
load();
setInterval(load,5*60*1000);
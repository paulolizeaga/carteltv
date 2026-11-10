const DATA_URL="./data/matches.json";
const $=id=>document.getElementById(id);
const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const timeFmt=new Intl.DateTimeFormat("es-ES",{timeZone:"Europe/Madrid",hour:"2-digit",minute:"2-digit",hour12:false});
const dateFmt=new Intl.DateTimeFormat("es-ES",{timeZone:"Europe/Madrid",weekday:"long",day:"numeric",month:"long",year:"numeric"});
let selectedDate="",matchData={matches:[]};
function madridToday(){const p=Object.fromEntries(new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Madrid",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date()).map(x=>[x.type,x.value]));return `${p.year}-${p.month}-${p.day}`;}
function shiftDate(value,amount){const d=new Date(value+"T12:00:00Z");d.setUTCDate(d.getUTCDate()+amount);return d.toISOString().slice(0,10);}
function render(){
 const today=madridToday(),chosen=new Date(selectedDate+"T12:00:00Z");
 $("today").textContent=dateFmt.format(chosen);
 $("previous-day").disabled=selectedDate<=shiftDate(today,-7);
 $("next-day").disabled=selectedDate>=shiftDate(today,14);
 $("today-button").hidden=selectedDate===today;
 const matches=(matchData.matches||[]).filter(m=>m.date===selectedDate).sort((a,b)=>new Date(a.start)-new Date(b.start));
 if(!matches.length){$("matches").innerHTML='<div class="empty">No hay eventos programados para este día.</div>';}
 else $("matches").innerHTML=matches.map(m=>{
  const live=m.status==="in",done=m.status==="post",time=m.start?timeFmt.format(new Date(m.start)):"— —",channel=m.channel||(done?"Emisión no disponible":"Canal por confirmar");
  return '<article class="match '+(live?"is-live":"")+'"><div class="kickoff">'+esc(time)+'<small>'+(live?"EN JUEGO":done?"FINAL":" ")+'</small></div><div class="match-body"><div class="teams"><div class="team"><img loading="lazy" src="'+esc(m.home_logo)+'" alt="" onerror="this.hidden=true"><span class="team-name">'+esc(m.home)+'</span></div><span class="vs">VS</span><div class="team away"><img loading="lazy" src="'+esc(m.away_logo)+'" alt="" onerror="this.hidden=true"><span class="team-name">'+esc(m.away)+'</span></div></div><div class="details"><span class="competition">'+esc(m.competition||"")+'</span><span class="channel '+(m.channel?"":"pending")+'">'+(m.channel_logo?'<img class="channel-logo" loading="lazy" src="'+esc(m.channel_logo)+'" alt="">':"")+esc(channel)+'</span></div></div></article>';
 }).join("");
 $("updated").textContent=matchData.updated_at?"Actualizado "+new Intl.DateTimeFormat("es-ES",{timeZone:"Europe/Madrid",hour:"2-digit",minute:"2-digit"}).format(new Date(matchData.updated_at)):"";
}
async function load(){try{const r=await fetch(DATA_URL+"?v="+Date.now(),{cache:"no-store"});if(!r.ok)throw Error("No se pudo cargar la cartelera");matchData=await r.json();render();}catch(e){$("matches").innerHTML='<div class="empty">No se ha podido cargar la cartelera.</div>';}}
$("previous-day").addEventListener("click",()=>{selectedDate=shiftDate(selectedDate,-1);render();});
$("next-day").addEventListener("click",()=>{selectedDate=shiftDate(selectedDate,1);render();});
$("today-button").addEventListener("click",()=>{selectedDate=madridToday();render();});
selectedDate=madridToday();load();setInterval(load,5*60*1000);

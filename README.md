# CartelTV · Mancave

Cartelera deportiva en formato cine para una pantalla horizontal. Muestra los eventos del día en horario peninsular (Europe/Madrid).

## Incluye
- LaLiga, Segunda División, Copa del Rey y Supercopa de España
- UEFA Champions League, Europa League y Conference League
- NHL: únicamente partidos de Toronto Maple Leafs
- Escudos, hora, estadio y canal cuando la fuente lo proporciona

## Actualización automática
GitHub Actions ejecuta `scraper/main.py` cada 30 minutos y publica la web mediante GitHub Pages.

## Activar GitHub Pages
En el repositorio, entra en **Settings → Pages** y selecciona **GitHub Actions** como Build and deployment source. Después ejecuta manualmente el workflow **Actualizar cartelera CartelTV** desde Actions.

## Fuentes y limitaciones
- ESPN scoreboard API: calendario, equipos, escudos, estadio y estado del evento.
- TVFutbol: enriquecimiento best-effort para canales españoles.
- ESPN hockey scoreboard: calendario y retransmisiones NHL cuando se publican.

Los canales que no se puedan verificar quedan vacíos y la web muestra «Emisión por confirmar». La extracción de canales desde páginas de terceros puede cambiar si cambia su estructura. Los datos se ofrecen como guía informativa; comprueba la programación del operador antes del partido.

## Desarrollo local
```bash
pip install -r scraper/requirements.txt
python scraper/main.py
python -m http.server 8000
``
Abre http://localhost:8000.

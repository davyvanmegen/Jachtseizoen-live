# Jachtseizoen Live

Een lokale Django webapp voor een live Jachtseizoen-spel met lobby, host-controls, realtime updates via Django Channels, browser-geolocation en Leaflet/OpenStreetMap.

## Installatie

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate
```

## Development server

```powershell
.\.venv\Scripts\python manage.py runserver
```

De server luistert standaard op je interne netwerk en print een aanklikbaar adres, bijvoorbeeld:

```text
Netwerkadres: http://192.168.1.83:8000/
```

Open dat adres op je telefoon zolang die op hetzelfde netwerk zit. Lokaal werkt `http://127.0.0.1:8000/` ook.

### Locatie op telefoon

Mobiele browsers blokkeren geolocation vaak op `http://192.168.x.x`. Voor snel lokaal testen in Chrome op Android:

1. Open `chrome://flags/#unsafely-treat-insecure-origin-as-secure`.
2. Zet de flag aan en voeg je adres toe, bijvoorbeeld `http://192.168.1.83:8000`.
3. Herstart Chrome.
4. Open de game opnieuw en tik op `Locatie delen`.

Voor echt gebruik is HTTPS nodig met een certificaat dat je telefoon vertrouwt.

Channels draait via ASGI. Met `daphne` kan dat ook expliciet:

```powershell
.\.venv\Scripts\daphne -b 0.0.0.0 -p 8000 jachtseizoen.asgi:application
```

## Spel testen

1. Maak op de homepagina een game aan als host.
2. Deel de 6-cijferige gamecode.
3. Join met meerdere browsers, incognito vensters of telefoons.
4. Laat de host start-runners kiezen of leeg laten voor willekeurige keuze.
5. Start het spel en geef locatiepermissie.
6. Tijdens de voorsprong worden locaties opgeslagen maar niet vrijgegeven.
7. Na de voorsprong zien runners periodieke snapshots van vluchters op de kaart.
8. Een vluchter klikt op `Ik ben gepakt` en wordt daarna runner.

## Demo data

```powershell
.\.venv\Scripts\python manage.py seed_demo
```

## Tests

```powershell
.\.venv\Scripts\python manage.py test
```

## Deploy op Render

Deze repo bevat `render.yaml`, zodat Render automatisch een gratis webservice en gratis Postgres database kan aanmaken.

1. Push de code naar GitHub.
2. Ga naar Render en kies `New` -> `Blueprint`.
3. Selecteer je GitHub repo.
4. Render leest `render.yaml` en maakt:
   - `jachtseizoen-live` webservice
   - `jachtseizoen-db` Postgres database
5. Deploy.

Render gebruikt:

```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
```

als build command en:

```bash
daphne -b 0.0.0.0 -p $PORT jachtseizoen.asgi:application
```

als start command.

De app verwacht deze environment variables:

```text
DEBUG=False
SECRET_KEY=<automatisch of zelf instellen>
DATABASE_URL=<Render Postgres connection string>
ALLOWED_HOSTS=.onrender.com
CSRF_TRUSTED_ORIGINS=https://*.onrender.com
SITE_PASSWORD=<wachtwoord dat spelers moeten invullen>
```

Render geeft automatisch HTTPS. Daardoor werkt geolocation op telefoons beter dan lokaal via `http://192.168.x.x`.

Laat `SITE_PASSWORD` leeg of verwijder de env var als je geen toegangsscherm wilt. Zet hem op Render in `Environment` op een wachtwoord dat je met je groep deelt.

## Implementatienotities

- Server time is leidend voor countdowns, statusovergangen en snapshot-intervallen.
- Ruwe locatiepings worden bewaard in `LocationPing`.
- Runners krijgen alleen vrijgegeven `ReleasedLocationSnapshot` records te zien.
- WebSockets publiceren lobby-, status-, caught- en snapshot-updates.
- Polling naar `/g/<code>/state/` blijft actief als simpele fallback en als periodieke snapshot-trigger.
- Browser-sessies koppelen een speler aan een game; hostrechten worden server-side gecontroleerd.

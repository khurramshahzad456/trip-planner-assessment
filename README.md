# RouteLog — HOS Trip Planner & ELD Daily Logs

RouteLog is a full-stack trip planner for U.S. property-carrying truck drivers. You enter the current location, pickup, dropoff and hours already used in the 70-hour cycle. RouteLog then:

- geocodes the three locations and calculates a **real driving route** (OpenStreetMap + OSRM),
- builds a **minute-by-minute Hours-of-Service schedule** with driving, 30-minute breaks, fuel stops, 10-hour rests, pickup and dropoff, and cycle recovery,
- shows the route and every planned stop on an **interactive map**, with a matching **chronological timeline**,
- fills out a **driver's daily log (ELD) sheet for each calendar day**, drawing the duty-status line on a 24-hour grid, with remarks, totals and a 70-hour recap,
- exports the log sheets to **PDF** or prints them.

> This is an assessment/demo tool built on the assumptions listed below. It is not legal advice.

---

## Features

| Area | What you get |
| --- | --- |
| Trip input | Address/city/ZIP autocomplete, cycle-hours validation (0–70), start date/time, optional driver/carrier/truck fields, **Load demo trip**, reset, recalculate |
| Routing | Two legs (current → pickup → dropoff), real distance and duration, route polylines, zoom-to-route |
| HOS engine | 11-hour driving limit, 14-hour window, 30-min break after 8 h of driving, 10-hour reset, rolling 70 h / 8-day cycle with recap **or** 34-hour restart, fuel every ≤ 1,000 mi, 1 h pickup and 1 h dropoff |
| Compliance audit | An independent checker re-verifies every generated schedule against each rule; the results are shown in the UI |
| Map | Colour-coded markers (blue current, orange pickup, red dropoff, green fuel, purple rest, amber break), legend, popups with arrival/departure/duration/reason, nearest real fuel station when available |
| Timeline | Every event with icon, type, start/end, duration, location, distance and reason, grouped by day |
| ELD logs | One sheet per day; events split at midnight; four duty-status rows drawn in SVG; per-row totals adding to 24:00; remarks; miles today / trip to date; cycle used, remaining and available tomorrow |
| Linked views | Click a stop on the map, an event in the timeline or a segment on a log graph, and the other views follow |
| Sharing | Every plan is saved; the URL `/trips/<id>` re-opens it; copy-link button |
| UX | Step-based loading state, friendly error states and toasts, responsive desktop/tablet/mobile layout, print stylesheet |

## Tech stack

- **Backend:** Python 3.12+, Django 5.2, Django REST Framework, PostgreSQL (SQLite locally), Gunicorn, WhiteNoise
- **Frontend:** React 19, Vite, Tailwind CSS 4, React Router, Leaflet / React-Leaflet, Lucide icons, jsPDF (loaded only when exporting)
- **Free map services:** Nominatim and Photon (geocoding), OSRM (routing; OpenRouteService HGV optional), OpenStreetMap tiles, Overpass (fuel-station lookup)
- **Hosting:** Render (API + Postgres, free tier) and Vercel (frontend)

## Architecture

```
locations ─► geocoding ─► routing ─► HOS scheduler ─► events ─► daily-log generator
                                          │              │              │
                                     compliance       map stops     ELD sheets
                                       audit         & timeline    (SVG / PDF)
```

The **event timeline from the scheduler is the single source of truth.** The map stops, timeline and daily logs are all derived from it on the server, so they cannot disagree. The frontend renders that payload and contains no HOS logic.

```
backend/
  config/                  settings (env-driven), urls, wsgi
  trips/
    models.py              Trip (inputs + saved plan JSON)
    serializers.py         request validation
    views.py               thin API views
    exceptions.py          uniform {"error": {code, message, fields}} responses
    services/
      hos_rules.py         ALL rule values and planning assumptions (one dataclass)
      hos_engine.py        HOSClock + CycleLedger (11/14/8-hour and 70/8 state)
      trip_scheduler.py    simulation that produces the event timeline
      fuel_planner.py      1,000-mile fuel tracking + Overpass station lookup
      log_generator.py     midnight splitting → daily logs, remarks, recap
      compliance.py        independent post-hoc rule audit
      routing_service.py   provider abstraction (OSRM, OpenRouteService)
      geocoding_service.py Nominatim / Photon geocode, autocomplete, reverse
      trip_planner.py      orchestration and response assembly
      geo.py, cache_utils.py
    tests/                 test_hos, test_scheduler, test_logs, test_api
frontend/
  src/
    pages/PlannerPage.jsx
    components/            trip/ summary/ map/ timeline/ logs/ common/ layout/
    hooks/                 useTripForm, useTripPlanner, useAutocomplete, useToast, …
    services/api.js
    utils/                 time, formatting, eventStyles, logGeometry, pdfExport
render.yaml                Render blueprint (API + Postgres)
frontend/vercel.json       Vercel config with SPA rewrites
```

## HOS rules and assumptions

All values live in [`backend/trips/services/hos_rules.py`](backend/trips/services/hos_rules.py) (`HOSRules`, `SpeedAssumptions`). The API serves the human-readable list at `/api/hos/assumptions/`, and the UI displays it.

- Property-carrying driver, **70 hours / 8 days**, no adverse driving conditions.
- **11 h** driving within a **14 h** window that starts at the first on-duty minute after **10 consecutive hours** off duty. Off-duty breaks do not pause the 14 h window.
- A **30-minute break** is required before 8 cumulative hours of driving. Under the 2020 rule, any 30 consecutive minutes not driving qualifies: a 30-min off-duty break, a fuel stop, or a pickup.
- **Fuel** stop (30 min, on duty) before the distance since the last fuel reaches **1,000 miles**. The truck starts full.
- **Pickup 1 h** and **dropoff 1 h**, on duty (not driving).
- 10-hour rests are logged in the **sleeper berth**; breaks and 34-hour restarts are logged off duty.
- **70-hour cycle:** the hours entered are assumed to be spread evenly over the previous 7 days, so they drop out of the rolling 8-day window one day at a time, as on a real recap. When the cycle runs out, the planner evaluates both "wait for hours to recap" and "34-hour restart" for each shortfall and keeps whichever gets the load delivered sooner.
- **Conservative planning:** on-duty work (pickup, dropoff, fuel) is never scheduled outside the 14-hour window or beyond 70 hours, even where the regulation would technically allow it.
- **Driving time** comes from the routing provider's duration for each leg, with the leg average capped at 65 mph (configurable). Distance divided by an assumed speed is never used to build the schedule.
- The driver starts the trip rested. All times are the driver's **home-terminal time**.

### How the scheduler works

`TripScheduler` simulates the trip in whole minutes. Before each chunk of driving it asks `HOSClock` how many minutes are legal (the minimum of the 11 h, 14 h, 8 h-break and 70 h limits) and asks `FuelTracker` how far the truck can go before 1,000 miles. It drives until the first limit binds, then inserts the matching stop (fuel, break, 10-hour rest, or cycle recovery) and repeats. `plan_schedule()` reruns this for each combination of recap and restart decisions and picks the earliest arrival. `compliance.audit_schedule()` then re-checks the finished timeline independently.

## API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/trips/plan/` | Plan a trip (returns the full plan and saves it) |
| `GET` | `/api/trips/<uuid>/` | Re-open a saved plan |
| `GET` | `/api/trips/` | Ten most recent plans |
| `GET` | `/api/geocode/autocomplete/?q=` | Address suggestions |
| `GET` | `/api/hos/assumptions/` | Active rules and assumptions |
| `GET` | `/api/health/` | Health check |

Request:

```json
{
  "current_location": "Los Angeles, CA",
  "pickup_location": "Phoenix, AZ",
  "dropoff_location": "Dallas, TX",
  "current_cycle_used": 20,
  "start_time": "2026-10-02T08:00",
  "driver_name": "", "carrier_name": "", "truck_number": ""
}
```

Optional fields named `<field>_coords` (`{lat, lng, label}`), sent when an autocomplete suggestion was chosen, skip geocoding for that field.

Response (abridged): `trip_summary`, `hos_summary` (cycle used / remaining / required, `status` of `FITS`, `RECOVERY_REQUIRED` or `NO_HOURS_AVAILABLE`, warnings, compliance checks), `route` (legs, geometry, bounds), `events`, `stops`, `daily_logs` (segments with `start_hour`/`end_hour`, totals, remarks, cycle recap), `assumptions`.

Errors always look like `{"error": {"code": "...", "message": "...", "fields": {...}}}`. Stack traces are never returned.

## Local setup

Prerequisites: Python 3.12+ and Node 20+.

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then set HTTP_USER_AGENT to your repo URL or email
python manage.py migrate
python manage.py createcachetable
python manage.py runserver      # http://127.0.0.1:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173 (proxies /api to :8000)
```

## Environment variables

**Backend** (`backend/.env.example`)

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Django secret (required when `DEBUG=False`) |
| `DEBUG` | `True` locally, `False` in production |
| `ALLOWED_HOSTS` | Comma-separated hosts; Render's hostname is added automatically |
| `DATABASE_URL` | Postgres URL; empty means SQLite |
| `CORS_ALLOWED_ORIGINS` / `CORS_ALLOWED_ORIGIN_REGEXES` | Frontend origins allowed to call the API |
| `ROUTING_PROVIDER` / `ROUTING_API_KEY` | `osrm` (no key) or `openrouteservice` (free key, truck profile) |
| `HTTP_USER_AGENT` | Identifies the app to OSM services. **Use a real URL or email; `example.com` is blocked.** |
| `OSRM_BASE_URL`, `NOMINATIM_BASE_URL`, `PHOTON_BASE_URL`, `OVERPASS_URLS` | Provider endpoints (self-hostable) |
| `ENABLE_FUEL_STATION_LOOKUP`, `ENABLE_REVERSE_GEOCODING` | Turn off optional enrichment calls |

**Frontend** (`frontend/.env.example`): `VITE_API_URL`, the deployed API base URL (leave empty locally).

## Testing

```bash
cd backend && python manage.py test trips    # 63 tests, no network access
cd frontend && npm test                       # geometry, formatting and validation
cd frontend && npm run build                  # production build
```

The backend tests cover the 30-minute break, 11-hour limit, 14-hour window, 10-hour reset, 70/8 cycle (65 h and exactly 70 h, recap and restart), fuel every ≤ 1,000 mi, pickup and dropoff durations, midnight splitting, multi-day logs, 24-hour totals, cycle-hour validation, API errors, and a sweep that runs every generated schedule through the compliance audit.

## Deployment

### 1. Backend on Render (free)

1. Push this repo to GitHub.
2. In Render, choose **New → Blueprint** and select the repo. `render.yaml` creates the Postgres database and the `eld-trip-planner-api` web service. It generates `SECRET_KEY`, runs `build.sh` (install, collectstatic, migrate, createcachetable) and serves the app with Gunicorn.
3. When prompted, set:
   - `HTTP_USER_AGENT`: for example `eld-trip-planner/1.0 (+https://github.com/<you>/eld-trip-planner)`
   - `CORS_ALLOWED_ORIGINS`: your Vercel URL (you can add it after step 2 of the frontend)
4. Check that `https://<service>.onrender.com/api/health/` returns `{"status":"ok"}`.

Render's free instances sleep when idle. The first request after a pause can take about a minute, and the UI tells the user when this happens.

### 2. Frontend on Vercel (free)

1. In Vercel, choose **Add New → Project**, import the repo and set **Root Directory** to `frontend`. The framework is detected as Vite.
2. Add the environment variable `VITE_API_URL=https://<service>.onrender.com`.
3. Deploy. `vercel.json` rewrites all routes to `index.html`, so shared `/trips/<id>` links work.
4. Put the Vercel URL in the backend's `CORS_ALLOWED_ORIGINS` and redeploy the backend. The blueprint also allows `*.vercel.app` preview URLs through `CORS_ALLOWED_ORIGIN_REGEXES`; tighten or remove that regex if you prefer.

## Demo walkthrough (3–5 min)

1. Click **Load demo trip** (Los Angeles → Phoenix → Dallas, 20 h used) and watch the step-based loading.
2. Walk through the summary: distance, driving time, days, stops, and the cycle bar and compliance checks.
3. On the map, click the fuel and rest markers, then pick a timeline event and watch the map fly to it.
4. Open the daily logs: the four-row graph, totals adding to 24:00, remarks, the 70-hour recap and the midnight split on Day 2. Download the PDF.
5. Try **65** cycle hours, or **70**, to see recap and restart handling, then show `hos_rules.py`, `trip_scheduler.py` and the tests.

## Limitations

- The public OSRM server uses a car profile. Truck-specific restrictions such as low bridges or hazmat routes are not modelled; set `ROUTING_PROVIDER=openrouteservice` with a free key for the HGV profile.
- Stop names ("near Pecos, TX") and nearest-fuel-station lookups are best effort with short deadlines. If a provider is slow, a stop is labelled by route mile instead. The schedule never depends on them.
- The sleeper-berth split provisions, the 16-hour short-haul exception and adverse-conditions extensions are intentionally not used, per the brief.

# Legacy Code Modernization Demo

This repository demonstrates migrating trade data from a legacy PostgreSQL
application to a cloud PostgreSQL database. It includes PostgreSQL, Kafka,
Debezium CDC, Python migration demos, automated tests, and a Streamlit
dashboard.

The commands below use Windows PowerShell.

## Legacy modernization concepts used

This project demonstrates four important legacy-code modernization concepts:

1. **Strangler Fig pattern**  
   New cloud functionality is introduced alongside the legacy application
   instead of replacing the entire system at once. Traffic and responsibility
   can be moved gradually while the legacy path remains available as a safety
   net.

2. **Change Data Capture (CDC)**  
   Changes made in the legacy PostgreSQL database are captured and propagated
   through Kafka and Debezium to the cloud PostgreSQL database. This supports
   near-real-time synchronization during the migration.

3. **Shadow validation**  
   Requests are evaluated using both the legacy and cloud rules, and their
   results are compared. Differences are recorded so the cloud implementation
   can be validated before it receives production traffic.

4. **Canary cutover**  
   Traffic is moved to the cloud implementation in controlled stages
   (`0%`, `5%`, `25%`, `50%`, and `100%`). Each stage is gated by validation,
   reconciliation, connector, and replication checks.

## Prerequisites

- Docker Desktop with Docker Compose
- Python 3.11 or newer
- Git

Docker Desktop must be running before starting the project.

## Project layout

| Path | Purpose |
| --- | --- |
| `docker-compose.yml` | PostgreSQL, Kafka, and Debezium services |
| `legacy-migration/requirements.txt` | Python dependencies |
| `legacy-migration/demo.py` | Local migration, validation, canary, and rollback demo |
| `legacy-migration/demo_kafka.py` | Kafka and Debezium CDC demos |
| `legacy-migration/frontend/dashboard_app.py` | Streamlit frontend |
| `legacy-migration/backend/` | Authentication, database, monitoring, and startup services |
| `legacy-migration/tests/test_migration.py` | Automated tests |
| `legacy-migration/debezium/legacy-connector.json` | Debezium connector configuration |

## First-time setup

Open PowerShell in the repository root:

```powershell
cd "D:\Transition X - V1\Legacy-Code-Modernization-V1"
```

Start all infrastructure:

```powershell
docker compose up -d
docker compose ps
```

Services use these host ports:

| Service | Host port | Purpose |
| --- | ---: | --- |
| `legacy_db` | `5433` | Legacy PostgreSQL database |
| `cloud_db` | `5434` | Cloud PostgreSQL database |
| `kafka` | `9092` | Kafka broker |
| `connect` | `8083` | Debezium Kafka Connect REST API |

Create the Python environment and install dependencies:

```powershell
cd ".\legacy-migration"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Set the connection variables for the current PowerShell session:

```powershell
$env:LEGACY_DSN = "postgresql://postgres:postgres@localhost:5433/legacy?connect_timeout=5"
$env:CLOUD_DSN = "postgresql://postgres:postgres@localhost:5434/cloud?connect_timeout=5"
$env:KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
```

## Run the local migration demo

From `legacy-migration`:

```powershell
python .\demo.py
```

This exercises legacy submission, CDC into the cloud store, shadow
validation, canary rollout, cloud failure fallback, and rollback. Successful
execution ends with:

```text
ALL CHECKS PASSED
```

Run the intentional negative test:

```powershell
python .\demo.py --negative-test
```

This injects a cloud fee-rounding defect and should show that cutover is
blocked.

## Register the Debezium connector

The direct Kafka flow only needs Kafka. The Debezium CDC flow also needs the
`connect` service and a registered connector.

Check that Kafka Connect is ready:

```powershell
Invoke-WebRequest -Uri "http://localhost:8083/" -UseBasicParsing
```

Register the connector:

```powershell
$connector = Get-Content ".\debezium\legacy-connector.json" -Raw
Invoke-RestMethod `
  -Uri "http://localhost:8083/connectors" `
  -Method Post `
  -ContentType "application/json" `
  -Body $connector
```

Check its status:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8083/connectors/legacy-trades-connector/status"
```

The connector and its task should report `RUNNING`.

If the connector already exists, update it:

```powershell
$config = (Get-Content ".\debezium\legacy-connector.json" -Raw | ConvertFrom-Json).config
Invoke-RestMethod `
  -Uri "http://localhost:8083/connectors/legacy-trades-connector/config" `
  -Method Put `
  -ContentType "application/json" `
  -Body ($config | ConvertTo-Json)
```

## Run the Kafka demo

From `legacy-migration`:

```powershell
python .\demo_kafka.py
```

The script contains a direct Kafka producer/consumer flow and a Debezium CDC
resume/replay flow. The Debezium flow requires connector registration first.
The CDC consumer reads the topic `legacy.public.trades`.

Successful execution includes:

```text
ALL KAFKA CHECKS PASSED
KAFKA CDC CHECKS PASSED
```

## Run the dashboard

The recommended path starts all required services and the dashboard through
Docker Compose:

```powershell
docker compose up --build
```

Open `http://localhost:8501` and sign in with `admin` / `migration`, unless
you override `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD`. Compose waits for
both PostgreSQL containers, initializes their tables and demo rows, and
restarts the dashboard if startup fails.

From `legacy-migration`:

```powershell
.\.venv\Scripts\Activate.ps1
$env:LEGACY_DSN = "postgresql://postgres:postgres@localhost:5433/legacy?connect_timeout=5"
$env:CLOUD_DSN = "postgresql://postgres:postgres@localhost:5434/cloud?connect_timeout=5"
python -m streamlit run .\frontend\dashboard_app.py
```

Open:

```text
http://localhost:8501
```

For a headless launch:

```powershell
python -m streamlit run .\frontend\dashboard_app.py `
  --server.headless true `
  --server.address localhost `
  --server.port 8501
```

The dashboard displays reconciliation, Debezium connector status,
replication-slot status, shadow validation, and the canary decision.

The dashboard opens with a login screen. For the local demo, the default
credentials are `admin` / `migration`. Set these environment variables before
starting Streamlit to use different credentials:

```powershell
$env:DASHBOARD_USERNAME = "your-user"
$env:DASHBOARD_PASSWORD = "your-password"
```

## Run automated tests

From `legacy-migration`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The tests use the PostgreSQL DSNs shown in the setup section.

## Stop and reset

Stop containers while preserving database volumes:

```powershell
cd "D:\Transition X - V1\Legacy-Code-Modernization-V1"
docker compose down
```

Stop containers and delete the demo database volumes:

```powershell
docker compose down -v
```

Use `docker compose down -v` only when a clean database state is required.

## Important data behavior

`Legacy` and `Cloud` create their tables when they start and truncate the demo
tables for repeatable runs. Running a demo can remove existing data in the two
demo databases. Do not point `LEGACY_DSN` or `CLOUD_DSN` at a shared or
production database.

## Troubleshooting

### Kafka connection failure

```powershell
docker compose ps
docker compose logs kafka --tail 100
docker compose up -d kafka
```

### Database connection failure

```powershell
docker compose ps
Test-NetConnection localhost -Port 5433
Test-NetConnection localhost -Port 5434
```

Re-export `LEGACY_DSN` and `CLOUD_DSN` in the current PowerShell session.

### Debezium connector failure

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8083/connectors/legacy-trades-connector/status"
docker compose logs connect --tail 150
```

The connector must use the Docker hostname `legacy_db`, not `localhost`.

### Dashboard dependency or syntax failure

```powershell
cd "D:\Transition X - V1\Legacy-Code-Modernization-V1\legacy-migration"
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m py_compile .\frontend\dashboard_app.py
```
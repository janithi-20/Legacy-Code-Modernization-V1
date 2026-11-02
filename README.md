# Legacy Code Modernization Demo

This repository demonstrates migrating trade data from a legacy PostgreSQL
application to a cloud PostgreSQL database. It includes PostgreSQL, Kafka,
Debezium CDC, Python migration demos, automated tests, and a Streamlit
dashboard.

The commands below use Windows PowerShell.

## Prerequisites

- Docker Desktop with Docker Compose
- Python 3.11 or newer for local development and tests
- Git

Start Docker Desktop before running any project commands.

## Quick start: run the complete application

Open PowerShell and run these commands from the repository root:

```powershell
cd "D:\Transition X - V1\Legacy-Code-Modernization-V1"
docker compose build dashboard
docker compose up -d legacy_db cloud_db kafka
docker compose ps
```

Wait until `legacy_db` and `cloud_db` show `healthy`. Then start Kafka
Connect and the dashboard:

```powershell
docker compose up -d connect dashboard
docker compose ps
```

Verify Kafka Connect and the dashboard:

```powershell
curl.exe http://localhost:8083/
Invoke-WebRequest -Uri "http://localhost:8501" -UseBasicParsing
```

Open [http://localhost:8501](http://localhost:8501) and sign in with:

```text
Username: admin
Password: migration
```

The dashboard displays reconciliation, Debezium connector status,
replication-slot status, shadow validation, and the canary decision.

To follow dashboard logs:

```powershell
docker compose logs -f dashboard
```

Press `Ctrl+C` to stop viewing logs. The containers continue running.

### Restart after frontend changes

If you change
[`legacy-migration/frontend/dashboard_app.py`](legacy-migration/frontend/dashboard_app.py),
rebuild and restart the dashboard:

```powershell
docker compose build dashboard
docker compose up -d dashboard
```

### Stop the application

Stop the containers while preserving database data:

```powershell
docker compose down
```

Stop the containers and delete the demo database volumes:

```powershell
docker compose down -v
```

Use `docker compose down -v` only when a clean database state is required.

## Service ports

| Service | Host port | Purpose |
| --- | ---: | --- |
| `legacy_db` | `5433` | Legacy PostgreSQL database |
| `cloud_db` | `5434` | Cloud PostgreSQL database |
| `kafka` | `9092` | Kafka broker |
| `connect` | `8083` | Debezium Kafka Connect REST API |
| `dashboard` | `8501` | Streamlit dashboard |

## Project layout

| Path | Purpose |
| --- | --- |
| `docker-compose.yml` | PostgreSQL, Kafka, Debezium, and dashboard services |
| `legacy-migration/requirements.txt` | Python dependencies |
| `legacy-migration/demo.py` | Local migration, validation, canary, and rollback demo |
| `legacy-migration/demo_kafka.py` | Kafka and Debezium CDC demos |
| `legacy-migration/frontend/dashboard_app.py` | Streamlit frontend |
| `legacy-migration/backend/` | Authentication, database, monitoring, and startup services |
| `legacy-migration/tests/test_migration.py` | Automated tests |
| `legacy-migration/debezium/legacy-connector.json` | Debezium connector configuration |

## First-time Python setup

Use this setup for the migration demos, Kafka demo, and automated tests:

```powershell
cd "D:\Transition X - V1\Legacy-Code-Modernization-V1\legacy-migration"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\requirements.txt
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

For local Python commands, export the database and Kafka settings in the same
PowerShell window:

```powershell
$env:LEGACY_DSN = "******localhost:5433/legacy?connect_timeout=5"
$env:CLOUD_DSN = "******localhost:5434/cloud?connect_timeout=5"
$env:KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
```

## Register the Debezium connector

Start the complete application first, then run these commands from
`legacy-migration`:

```powershell
cd "D:\Transition X - V1\Legacy-Code-Modernization-V1\legacy-migration"
curl.exe http://localhost:8083/
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

The connector configuration must use the Docker hostname `legacy_db`, not
`localhost`, for the source database.

## Run the migration demo

From `legacy-migration`, with the Docker databases running:

```powershell
python .\demo.py
```

Successful execution ends with:

```text
ALL CHECKS PASSED
```

Run the intentional negative test:

```powershell
python .\demo.py --negative-test
```

This injects a cloud fee-rounding defect and should show that cutover is
blocked.

## Run the Kafka demo

From `legacy-migration`:

```powershell
python .\demo_kafka.py
```

The direct Kafka flow requires Kafka. The Debezium CDC flow also requires the
`connect` service and a registered connector. The CDC consumer reads the
`legacy.public.trades` topic.

Successful execution includes:

```text
ALL KAFKA CHECKS PASSED
KAFKA CDC CHECKS PASSED
```

To inspect messages directly from the Kafka container:

```powershell
docker exec kafka /opt/kafka/bin/kafka-console-consumer.sh `
  --bootstrap-server localhost:9092 `
  --topic legacy.public.trades `
  --from-beginning `
  --max-messages 3
```

## Run automated tests

From `legacy-migration`:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

The tests use the PostgreSQL DSNs shown in the Python setup section.

## Run Streamlit directly for development

Use this mode when you want Streamlit to reload while editing the frontend.
The Docker databases must be running:

```powershell
cd "D:\Transition X - V1\Legacy-Code-Modernization-V1"
docker compose up -d legacy_db cloud_db
cd ".\legacy-migration"
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

Set the environment variables:

```powershell
$env:LEGACY_DSN = "******localhost:5433/legacy?connect_timeout=5"
$env:CLOUD_DSN = "******localhost:5434/cloud?connect_timeout=5"
$env:CONNECTOR_URL = "http://localhost:8083/connectors/legacy-trades-connector/status"
$env:DASHBOARD_USERNAME = "admin"
$env:DASHBOARD_PASSWORD = "migration"
```

Initialize the databases and start Streamlit:

```powershell
.\.venv\Scripts\python.exe -m backend.bootstrap
.\.venv\Scripts\python.exe -m streamlit run .\frontend\dashboard_app.py `
  --server.headless true `
  --server.address localhost `
  --server.port 8501
```

Open [http://localhost:8501](http://localhost:8501). Press `Ctrl+C` to stop
the local Streamlit process.

## Demo walkthrough: run order

Use this section to run the complete demo in order. It assumes Docker Desktop
is running, `legacy_db`, `cloud_db`, and `kafka` are already up, the Python
environment is set up (see [First-time Python setup](#first-time-python-setup)),
and the Debezium connector is registered (see
[Register the Debezium connector](#register-the-debezium-connector)).

### 1. Start Kafka Connect and check the containers

```powershell
docker compose up -d connect
docker compose ps
```

### 2. Check the Debezium connector status

```powershell
curl.exe http://localhost:8083/connectors/legacy-trades-connector/status
```

The connector and its task should report `RUNNING`.

### 3. Run the tests and the migration demos

```powershell
cd legacy-migration
python -m pytest -v
python demo.py
python demo.py --negative-test
```

`python demo.py` should end with `ALL CHECKS PASSED`. The negative test
injects a fee-rounding defect and should show that cutover is blocked.

### 4. Run the Kafka demo

```powershell
python demo_kafka.py
```

Successful execution includes `ALL KAFKA CHECKS PASSED` and
`KAFKA CDC CHECKS PASSED`.

### 5. Inspect the CDC messages in Kafka

```powershell
docker exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic legacy.public.trades --from-beginning --max-messages 3
```

This prints the first three change events from the `legacy.public.trades`
topic.

### 6. Start the dashboard (in a new terminal)

Open a **new terminal** and run:

```powershell
cd "D:\Transition X - V1\Legacy-Code-Modernization-V1\legacy-migration"
python -m streamlit run frontend/dashboard_app.py
```

Open [http://localhost:8501](http://localhost:8501) and sign in with
`admin` / `migration`. Keep the first terminal open for the other commands.

If the Docker `dashboard` container is also running, it already uses port
`8501`. Stop it with `docker compose stop dashboard`, or start the local
dashboard on another port with `--server.port 8502`.

## Troubleshooting

### Check all services

```powershell
docker compose ps
```

`legacy_db` and `cloud_db` should be `healthy`. `connect` should be
`healthy` before registering the connector.

### Kafka Connect is restarting

Kafka Connect requires Kafka to be running. Start the services in this order:

```powershell
docker compose up -d kafka
docker compose up -d connect
curl.exe http://localhost:8083/
docker compose logs --tail 100 connect
```

### Database connection failure

```powershell
docker compose ps
Test-NetConnection localhost -Port 5433
Test-NetConnection localhost -Port 5434
docker compose logs --tail 100 legacy_db
docker compose logs --tail 100 cloud_db
```

Re-export `LEGACY_DSN` and `CLOUD_DSN` in the current PowerShell session.

### Debezium connector failure

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8083/connectors/legacy-trades-connector/status"
docker compose logs --tail 150 connect
```

### Dashboard dependency or syntax failure

```powershell
cd "D:\Transition X - V1\Legacy-Code-Modernization-V1\legacy-migration"
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\.venv\Scripts\python.exe -m py_compile .\frontend\dashboard_app.py
docker compose logs --tail 150 dashboard
```

## Important data behavior

The bootstrap process creates the application tables and inserts demo rows
when the databases are empty. Do not point `LEGACY_DSN` or `CLOUD_DSN` at a
shared or production database.

## Modernization concepts demonstrated

1. **Strangler Fig pattern** - Cloud functionality is introduced alongside the
   legacy application so traffic can move gradually.
2. **Change Data Capture (CDC)** - Debezium captures changes from legacy
   PostgreSQL and publishes them through Kafka.
3. **Shadow validation** - Legacy and cloud rules are evaluated together and
   their results are compared before cutover.
4. **Canary cutover** - Traffic moves through controlled stages: `0%`, `5%`,
   `25%`, `50%`, and `100%`.

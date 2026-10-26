# Legacy Code Modernization Project Guide

## 1. What this project is for

This project is a controlled proof of concept for modernizing a legacy trade
reporting function without replacing the whole system in one step.

The business function used in the demonstration is:

- Accepting and storing trades
- Calculating the trade notional
- Calculating a transaction fee
- Keeping a legacy store and a cloud-side store consistent

The project demonstrates how a legacy implementation can continue operating
while a cloud-side implementation is synchronized, compared, and moved
through a controlled cutover process.

This is a local development PoC. It uses synthetic data and Docker services.
It is not a production deployment and does not claim production throughput,
zero downtime, or zero data loss.

## 2. The four modernization concepts

### 2.1 Strangler Fig pattern

The new cloud-side functionality is introduced beside the legacy path. The
legacy path remains available while the cloud path is validated.

In this project:

- `app.legacy.service.Legacy` represents the legacy store.
- `app.cloud.service.Cloud` represents the cloud-side store.
- `app.router.routing.Router` decides whether a request goes to legacy or
  cloud.
- The router starts at 0% cloud traffic and can progress through 5%, 25%,
  50%, and 100%.
- If the cloud path fails, the router returns traffic to legacy.

The dashboard can demonstrate the gate decision, but it does not control a
live production router.

### 2.2 Change Data Capture (CDC)

CDC copies committed changes from the legacy database to the cloud database.
The project demonstrates two CDC paths:

1. **Application CDC for deterministic migration tests**
   - The legacy service writes a trade and a change-log record together.
   - `app.cdc.consumer.run_cdc` reads changes after the cloud offset.
   - The cloud store applies each event.

2. **Kafka/Debezium CDC**
   - PostgreSQL logical changes are captured by Debezium.
   - Debezium publishes events to Kafka topic `legacy.public.trades`.
   - `app.cdc.kafka_consumer.CdcConsumer` consumes and applies the events.
   - The consumer commits its Kafka offset after applying an event.

The Docker services are defined in `docker-compose.yml`:

- `legacy_db`: PostgreSQL 16 on host port `5433`
- `cloud_db`: PostgreSQL 16 on host port `5434`
- `kafka`: Apache Kafka 3.8.0 on host port `9092`
- `connect`: Debezium Connect 2.7 on host port `8083`

### 2.3 Shadow validation

Shadow validation evaluates the same request with both the legacy and cloud
rules and compares the results before traffic is moved.

The implementation is in `app.validation.shadow.Shadow`.

For example:

```text
quantity = 100
price = 25.50
notional = 2550.00
normal fee = 1.28
```

The negative test deliberately uses a cloud rounding defect:

```text
legacy fee = 1.28
cloud fee  = 1.27
```

When the defect is injected, 15 of 30 comparisons mismatch and the cutover
gate is blocked.

### 2.4 Canary cutover

Canary cutover moves traffic in controlled steps instead of switching
everything at once.

The steps are implemented in `app.migration.canary`:

```text
0% → 5% → 25% → 50% → 100%
```

The next step is allowed only when shadow validation has run, has zero
mismatches and errors, and replication lag is zero.

The router uses a stable hash of the request ID to decide which path receives
a request. If cloud submission fails, it resets traffic to legacy.

## 3. How the project is implemented

### 3.1 Trade calculation and persistence

`app.common.calc` calculates the notional and fee using `Decimal`:

```text
notional = quantity × price
fee = notional × 0.0005
```

Normal mode uses half-up rounding. The optional bug mode uses truncation to
simulate a cloud implementation defect.

`TradeStore` creates the tables and provides common persistence behavior.
The demonstration stores:

- `trades`
- `change_log`
- `cdc_offset`

The demo services initialize and truncate their demonstration tables for
repeatable runs. They must not be connected to a shared or production
database.

### 3.2 Legacy and cloud services

`app.legacy.service.Legacy`:

- Receives trade submissions.
- Calculates the legacy result.
- Stores the trade.
- Writes a change-log event.

`app.cloud.service.Cloud`:

- Receives cloud-side submissions.
- Applies CDC events.
- Uses sequence-aware upsert behavior.
- Ignores duplicate or older events for the same trade.

### 3.3 Reconciliation

`app.validation.reconciliation.reconcile` compares the two stores and reports:

- `missing`: present in legacy but absent in cloud
- `extra`: present in cloud but absent in legacy
- `different`: present in both but with different values

An empty result means:

```text
missing=[]
extra=[]
different=[]
```

### 3.4 Fallback and rollback

`app.router.routing.Router` falls back to legacy when cloud submission raises
an error.

`app.migration.rollback.rollback`:

- Resets the router to 0% cloud traffic.
- Finds trades accepted only by the cloud.
- Copies those trades back to legacy.

The normal demo verifies that 105 of 105 trades are preserved after a
simulated cloud failure and rollback.

## 4. What happened during development and verification

### 4.1 Automated tests

The current PostgreSQL test run produced:

```text
10 passed in 1.79s
```

The tests cover:

- Fee rounding
- Legacy persistence
- CDC replication
- Duplicate events
- Out-of-order events
- Consumer resume
- Missing-record detection
- Bug detection
- Canary gating
- Cloud outage and rollback

Evidence:

- `legacy-migration/evidence_verified/1_postgresql_tests.txt`

### 4.2 Normal migration demo

Running `demo.py` produced:

- CDC lag: `0`
- Shadow comparisons: `70`
- Matches: `70`
- Mismatches: `0`
- Errors: `0`
- Canary stages: `5%`, `25%`, `50%`, `100%`
- Reconciliation: clean
- Trades preserved: `105 of 105`
- Result: `ALL CHECKS PASSED`

Evidence:

- `legacy-migration/evidence_verified/2_normal_demo.txt`

### 4.3 Negative validation demo

Running `demo.py --negative-test` injected the cloud fee-rounding defect:

- Comparisons: `30`
- Matches: `15`
- Mismatches: `15`
- Errors: `0`
- Cutover: `BLOCKED`

This proves that the validation gate can prevent a known cloud calculation
defect from reaching the canary stage.

Evidence:

- `legacy-migration/evidence_verified/3_negative_test.txt`

### 4.4 Kafka and Debezium demo

The Kafka/Debezium demo verified:

- Direct Kafka flow: `5 of 5` messages received
- Initial CDC application: `20 of 20` trades
- Consumer outage: `10` trades temporarily missing
- Consumer restart: `10 of 10` trades applied
- Duplicate replay: `0` changes
- Final trade count: `30`
- Final reconciliation: clean
- Result: `KAFKA CDC CHECKS PASSED`

Evidence:

- `legacy-migration/evidence_verified/4_kafka_debezium.txt`

### 4.5 Environment validation

The verified local environment contained:

- PostgreSQL 16 legacy container
- PostgreSQL 16 cloud container
- Apache Kafka 3.8.0
- Debezium Connect 2.7
- Connector state: `RUNNING`
- Connector task 0: `RUNNING`
- Dashboard Python compilation: passed

Evidence:

- `legacy-migration/evidence_verified/5_environment.txt`

## 5. Dashboard user interface

The Streamlit frontend is implemented in:

`legacy-migration/frontend/dashboard_app.py`

It is started with:

```powershell
cd "D:\Transition X - V1\Legacy-Code-Modernization-V1\legacy-migration"
.\.venv\Scripts\Activate.ps1
python -m streamlit run .\frontend\dashboard_app.py
```

Open:

```text
http://localhost:8501
```

### 5.1 Sidebar controls

#### Auto-refresh every 5 seconds

When enabled, the live-status panel refreshes periodically. This allows
connector, replication, and reconciliation changes to be observed without
manually refreshing the page.

#### Refresh now

Triggers a Streamlit rerun so the current database and connector state can be
read again.

### 5.2 Live status

The live-status panel reads both databases using read-only queries.

#### Legacy trades

The number of trades currently present in the legacy `trades` table.

#### Cloud trades

The number of trades currently present in the cloud `trades` table.

#### Missing in cloud

The number of legacy trades not found in cloud. A non-zero value indicates
incomplete synchronization.

#### Different rows

The number of records that exist in both stores but contain different values.

#### Debezium connector

Reads the connector status from:

```text
http://localhost:8083/connectors/legacy-trades-connector/status
```

Expected healthy value:

```text
RUNNING
```

#### Replication slot

Reads the `legacy_slot` state from PostgreSQL. An active slot indicates that
the connector is connected to the legacy database.

#### WAL lag

Shows the PostgreSQL write-ahead-log lag in bytes for the replication slot.
This is an operational indicator, not a user-traffic latency measurement.

#### Trade comparison chart

Displays the legacy and cloud trade counts visually.

#### Reconciliation message

Healthy state:

```text
Cloud matches legacy: nothing missing, extra or different.
```

Unhealthy state reports the missing, extra, and different counts.

#### Cutover decision

The dashboard evaluates four checks:

1. Debezium connector and task are running.
2. Replication slot is active.
3. Cloud matches legacy.
4. Shadow validation has run with zero mismatches.

All four checks must pass for:

```text
CUTOVER ALLOWED
```

If any check fails:

```text
CUTOVER BLOCKED
```

### 5.3 Shadow validation

The user selects the number of comparisons and can optionally enable:

```text
Inject cloud rounding bug (negative test)
```

When the user clicks **Run shadow validation**, each synthetic request is
evaluated by the legacy and cloud rules.

The dashboard displays:

- Compared
- Matched
- Mismatched
- Errors
- Mismatch details when available

Verified healthy result:

```text
Compared: 30
Matched: 30
Mismatched: 0
Errors: 0
```

Verified negative result:

```text
Compared: 30
Matched: 15
Mismatched: 15
Errors: 0
CUTOVER BLOCKED
```

### 5.4 Canary rollout gate demo

The dashboard displays the current simulated cloud traffic percentage.

The **Advance one step** button attempts:

```text
0% → 5% → 25% → 50% → 100%
```

The advance operation is blocked when the validation gate fails or live data is
unavailable.

The **Roll back to 0%** button resets the dashboard’s simulated percentage to
zero. This demonstrates the gate state; it does not change production traffic.

## 6. Captured dashboard scenarios

The following screenshots are stored in:

`legacy-migration/evidence_verified/`

### Healthy cutover

`dashboard_healthy_cutover.png`

Observed:

- Legacy: 30
- Cloud: 30
- Missing: 0
- Different: 0
- Connector: `RUNNING`
- Slot: active
- Shadow: 30/30 matched
- Decision: `CUTOVER ALLOWED`

### Rounding defect

`dashboard_rounding_bug_blocked.png`

Observed:

- Bug injection enabled
- 30 comparisons
- 15 matches
- 15 mismatches
- Decision: `CUTOVER BLOCKED`

### Connector unavailable

`dashboard_connector_unavailable.png`

Observed after temporarily stopping Debezium Connect:

- Connector: `UNREACHABLE`
- Slot: inactive
- Connector check: failed
- Slot check: failed
- Decision: `CUTOVER BLOCKED`

### Missing cloud trade

`dashboard_missing_trade.png`

Observed after deliberately deleting one cloud trade:

- Legacy: 30
- Cloud: 29
- Missing in cloud: 1
- Reconciliation: failed
- Decision: `CUTOVER BLOCKED`

The database was restored afterward by running the normal demo again.

Scenario index:

- `legacy-migration/evidence_verified/dashboard_scenarios.txt`

## 7. Architecture summary

The verified local pipeline is:

```text
Legacy application
        |
        v
Legacy PostgreSQL
        |
        v
Debezium Connect
        |
        v
Kafka topic: legacy.public.trades
        |
        v
Python CDC consumer
        |
        v
Cloud PostgreSQL
```

Validation and control components observe or control the migration PoC:

```text
Legacy + Cloud stores
        |
        +--> Reconciliation
        +--> Shadow validation
        +--> Canary gate
        +--> Router fallback
        +--> Rollback
        +--> Streamlit dashboard
```

Architecture image:

- `legacy-migration/evidence_verified/architecture_diagram.png`

## 8. AWS and Amazon RDS clarification

The current reproducible project configuration uses local Docker PostgreSQL
for both the legacy and cloud databases:

```text
legacy_db: localhost:5433
cloud_db:  localhost:5434
```

Some older files under `evidence_cloud/` are labelled “Amazon RDS”, but they
do not provide a current RDS endpoint or independent AWS evidence. Amazon RDS
execution is therefore not treated as verified in this guide.

The accurate statement is:

> The verified implementation is a local Docker-based PostgreSQL cloud-target
> proof of concept. Amazon RDS execution is not verified by the current
> repository evidence.

## 9. What remains to be done for production readiness

- Run load and latency tests.
- Measure events per second and replication delay.
- Test high concurrency and network failures.
- Add monitoring and alerting for connector failure and replication lag.
- Perform a formal security review.
- If AWS is required, run the tests against an actual RDS endpoint and retain
  redacted RDS, network, security-group, and test-output evidence.

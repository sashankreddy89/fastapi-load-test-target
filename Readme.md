# FastAPI Load Test Target

A production-style FastAPI application built as a realistic target for Locust load testing. It runs a full microservices-inspired stack — FastAPI, PostgreSQL, and Kafka — inside Docker Compose, and includes simulation hooks to inject artificial errors and latency so Locust has something meaningful to measure.

---

## Tech Stack

| Layer       | Technology                        |
|-------------|-----------------------------------|
| API         | FastAPI + Gunicorn + UvicornWorker |
| Database    | PostgreSQL 15 via SQLAlchemy ORM  |
| Messaging   | Apache Kafka (Confluent 7.6.0)    |
| Auth        | JWT via PyJWT + OAuth2            |
| Container   | Docker + Docker Compose           |

---

## Project Structure

```
derms-model/
├── main.py              # FastAPI app — all endpoints, middleware, lifespan
├── derms_models.py      # SQLAlchemy ORM models (Users, Assets)
├── derms_schemas.py     # Pydantic request and response schemas
├── derms_db.py          # Database engine and get_db dependency
├── derms_sec.py         # Password hashing, JWT creation and verification
├── requirements.txt     # Python dependencies
├── Dockerfile           # Production image — Gunicorn with UvicornWorker
├── .dockerignore        # Excludes venv, pycache, test files from image
├── docker-compose.yml   # Full stack — FastAPI + PostgreSQL + Kafka
└── .env                 # Environment variables — never commit this file
```

---

## Environment Variables

All configuration is passed via environment variables. The `.env` file is read automatically by Docker Compose. For local development without Docker, export them in your shell.

### Required for all run modes

| Variable              | Description                                    | Example                        |
|-----------------------|------------------------------------------------|--------------------------------|
| `DB_TYPE`             | SQLAlchemy dialect                             | `postgresql`                   |
| `DB_USERNAME`         | PostgreSQL username                            | `derms`                        |
| `DB_PASSWORD`         | PostgreSQL password                            | `derms123`                     |
| `DB_SERVER_URL`       | PostgreSQL hostname                            | `localhost` or `postgres`      |
| `DB_SERVER_PORT`      | PostgreSQL port                                | `5432`                         |
| `DB_NAME`             | PostgreSQL database name                       | `dermsdb`                      |
| `ENGINE_ECHO`         | Log all SQL to stdout (`true` or `false`)      | `false`                        |
| `JWT_SECRET_KEY`      | Secret used to sign and verify JWT tokens      | `my-super-secret-key`          |
| `KAFKA_BOOTSTRAP_URL` | Kafka broker hostname                          | `localhost` or `kafka`         |
| `KAFKA_BOOTSTRAP_PORT`| Kafka broker port                              | `9092`                         |

> **Note on DB_SERVER_URL and KAFKA_BOOTSTRAP_URL:** When running inside Docker Compose, use the service name (`postgres`, `kafka`). These are internal DNS names on the Compose network. When running locally outside Docker, use `localhost`.

### Required by Docker Compose only

| Variable        | Description                         | Example                  |
|-----------------|-------------------------------------|--------------------------|
| `POSTGRES_USER` | PostgreSQL superuser for init       | `derms`                  |
| `POSTGRES_PASSWORD` | PostgreSQL superuser password   | `derms123`               |
| `POSTGRES_DB`   | Database to create on first start   | `dermsdb`                |
| `CLUSTER_ID`    | Kafka KRaft cluster ID              | any valid base64 string  |

### Simulation hooks (optional)

These are off by default. Set them only when you want to simulate a stressed system — for example during Locust runs.

| Variable                  | Description                                                  | Default |
|---------------------------|--------------------------------------------------------------|---------|
| `SIMULATE_ERROR_RATE`     | Float 0.0–1.0. Fraction of requests that return 500.        | `0`     |
| `SIMULATE_SLOW_ENDPOINT_MS` | Integer milliseconds. All requests are delayed by this amount. | `0` |

Example: `SIMULATE_ERROR_RATE=0.1` means 10% of requests return a simulated 500 error.

---

## Running the Application

There are three ways to run this application. Docker Compose is the recommended approach because it starts all three services together with correct networking and health checks.

### Option 1 — Local development (no Docker)

Use this when you want to iterate quickly on code without rebuilding a Docker image. You need PostgreSQL and Kafka running separately.

```bash
cd derms-model
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export DB_TYPE=postgresql
export DB_USERNAME=derms
export DB_PASSWORD=derms123
export DB_SERVER_URL=localhost
export DB_SERVER_PORT=5432
export DB_NAME=dermsdb
export ENGINE_ECHO=false
export JWT_SECRET_KEY=my-super-secret-key
export KAFKA_BOOTSTRAP_URL=localhost
export KAFKA_BOOTSTRAP_PORT=9092

uvicorn main:app --reload --port 8000
```

### Option 2 — Docker container only

Use this when you want to test the production image in isolation. PostgreSQL and Kafka must already be running on the host.

```bash
# Build the image
docker build -t fastapi-app:latest .

# Run the container
docker run -d --name fastapi-app -p 8000:8000 --network host \
  -e DB_TYPE=postgresql \
  -e DB_USERNAME=derms \
  -e DB_PASSWORD=derms123 \
  -e DB_SERVER_URL=localhost \
  -e DB_SERVER_PORT=5432 \
  -e DB_NAME=dermsdb \
  -e ENGINE_ECHO=false \
  -e JWT_SECRET_KEY=my-super-secret-key \
  -e KAFKA_BOOTSTRAP_URL=localhost \
  -e KAFKA_BOOTSTRAP_PORT=9092 \
  fastapi-app:latest
```

> **Why --network host:** Inside a container, `localhost` refers to the container's own network, not the host machine. `--network host` makes the container share the host's network stack so it can reach PostgreSQL and Kafka on `localhost`.

### Option 3 — Docker Compose (recommended)

This starts PostgreSQL, Kafka, and FastAPI together. FastAPI waits for both services to pass their health checks before starting. All configuration is read from the `.env` file in the same directory.

```bash
cd derms-model

# First run or after any code change
docker compose up --build

# Subsequent runs when code has not changed
docker compose up

# Stop and preserve the database
docker compose down

# Stop and wipe the database (clean slate)
docker compose down -v
```

> **Important:** Always run `docker compose up --build` after changing any Python file. Docker Compose caches the image and will not pick up code changes unless you explicitly rebuild.

### Option 4 — Docker Compose with simulation hooks

Pass simulation variables inline before the command. They override the defaults without touching the `.env` file.

```bash
# 10% error rate and 500ms delay on all requests
SIMULATE_ERROR_RATE=0.1 SIMULATE_SLOW_ENDPOINT_MS=500 docker compose up

# 100% error rate — every request returns 500
SIMULATE_ERROR_RATE=1.0 docker compose up

# 2 second delay on all requests — no errors
SIMULATE_SLOW_ENDPOINT_MS=2000 docker compose up
```

---

## API Endpoints

The application runs on port `8000`. All authenticated endpoints require a JWT token in the `Authorization: Bearer <token>` header.

### Get a token

Register a user and log in to get a token. Store the token in a shell variable for convenience.

```bash
# Register
curl -s -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}'

# Login and capture token
TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -d "username=testuser&password=testpass123" | \
  python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

> **Why login uses form data not JSON:** The `/login` endpoint uses OAuth2PasswordRequestForm which reads `application/x-www-form-urlencoded` data. Pass credentials with `-d` not `-d '{...}'` with a Content-Type JSON header.

### Endpoints

**GET /health** — No authentication required.
```bash
curl -s http://localhost:8000/health
```

**POST /register** — Create a new user.
```bash
curl -s -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}'
```

**POST /login** — Returns a JWT token.
```bash
curl -s -X POST http://localhost:8000/login \
  -d "username=testuser&password=testpass123"
```

**GET /assets** — Returns all assets. Auth required.
```bash
curl -s http://localhost:8000/assets \
  -H "Authorization: Bearer $TOKEN"
```

**GET /assets/{id}** — Returns a single asset by UUID. Auth required.
```bash
curl -s http://localhost:8000/assets/250e9995-decc-40dd-a973-f817cd7c3f8c \
  -H "Authorization: Bearer $TOKEN"
```

**POST /assets** — Creates a new asset. Auth required. `owner_id` is always set from the JWT — never from the request body.
```bash
curl -s -X POST http://localhost:8000/assets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Solar Panel 1", "asset_type": "solar", "status": "active"}'
```

Valid `asset_type` values: `solar`, `battery`, `ev`, `wind`  
Valid `status` values: `active`, `inactive`, `fault`, `maintenance`

**PUT /assets/{id}/status** — Updates asset status and publishes a Kafka event. Auth required.
```bash
curl -s -X PUT http://localhost:8000/assets/250e9995-decc-40dd-a973-f817cd7c3f8c/status \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "maintenance"}'
```

**GET /metrics** — Returns asset counts by status and type. Auth required.
```bash
curl -s http://localhost:8000/metrics \
  -H "Authorization: Bearer $TOKEN"
```

---

## Kafka Verification

Every `PUT /assets/{id}/status` request publishes an event to the `asset-status-changes` topic. The event contains the asset ID, old status, new status, and timestamp.

To verify events are being published, run the consumer from your VM (outside Docker):

```bash
# From the kafka/ directory
python kafka/consumer_demo.py
```

Or using the Kafka CLI directly against the external port:

```bash
docker exec derms-model-kafka-1 \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic asset-status-changes \
  --from-beginning
```

To list all topics:

```bash
docker exec derms-model-kafka-1 \
  kafka-topics --bootstrap-server localhost:9092 --list
```

---

## Consumer Lag Observation

Consumer lag is the number of messages a consumer group is behind the latest offset. High lag means the consumer is not keeping up with the producer — a common performance issue in production systems.

To observe lag during a Locust run, run this in a separate terminal:

```bash
watch -n 2 "docker exec derms-model-kafka-1 \
  kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe \
  --all-groups"
```

This refreshes every 2 seconds and shows each consumer group, partition, current offset, log end offset, and lag. If lag is growing during a load test, the consumer is falling behind.

---

## Key Design Decisions

**Database is the source of truth.** The PUT endpoint commits the status change to PostgreSQL before publishing to Kafka. If Kafka publish fails, the database change is preserved. The event will be missing but the data is not lost.

**One Kafka producer per process.** The producer is created once in the FastAPI lifespan and stored on `app.state`. Creating a producer per request would open and close connections on every request — expensive and unnecessary.

**Gunicorn with UvicornWorker in production.** The Dockerfile uses Gunicorn as the process manager with UvicornWorker for each worker process. This gives process-level isolation, automatic worker restart on crash, and the async performance of Uvicorn.

**Simulation hooks use middleware.** The error rate and slow endpoint hooks are implemented as FastAPI middleware — a single function that wraps every request. This means the hooks apply to all endpoints without touching any endpoint code.

**asyncio.sleep not time.sleep for latency injection.** FastAPI runs on an async event loop. `time.sleep` blocks the entire event loop — all concurrent requests freeze while one request is sleeping. `asyncio.sleep` yields control back to the event loop so other requests continue being served during the sleep.

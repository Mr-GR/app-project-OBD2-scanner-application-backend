# App Projet OBD2 Scanner Backend

A local AI-powered help desk agent using:

- **FastAPI** for backend with hybrid LLM classification
- **PostgreSQL** database with environment management
- **Flutter** (mobile/web) UI
- **ELM327** OBD2 scanner support
- **Together AI** integration for smart automotive diagnostics

---

## Environment Management

This project uses environment-specific configurations for clean development, staging, and production deployments.

### Quick Start Scripts

| Script | Purpose | Description |
|--------|---------|-------------|
| `./scripts/deploy.sh [env]` | **Deploy to environment** | Start the application in development (native), staging (Docker), or production (Docker) |
| `source ./scripts/env.sh [env]` | **Load environment** | Load environment variables for manual development work |
| `python test_db.py` | **Test database** | Verify PostgreSQL connection and create tables |

### Environment Setup

```bash
# Development (Local PostgreSQL + Native Python)
./scripts/deploy.sh development

# Staging (Docker containers)
./scripts/deploy.sh staging

# Production (Docker containers)
./scripts/deploy.sh production
```

### Manual Development

```bash
# Load development environment variables
source ./scripts/env.sh development

# Start development server
python main.py
```

---

## Initial Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup PostgreSQL (Local Development)

```bash
# Install PostgreSQL
brew install postgresql
brew services start postgresql

# Create database and user
createdb obd2_scanner
psql obd2_scanner -c "CREATE USER obd2_user WITH PASSWORD 'obd2_password';"
psql obd2_scanner -c "GRANT ALL PRIVILEGES ON DATABASE obd2_scanner TO obd2_user;"
```

### 3. Configure Environment

```bash
# Copy and edit development environment
cp environments/development/.env environments/development/.env.local
# Add your TOGETHER_API_KEY to the .env file
```

### 4. Test Database Connection

```bash
python test_db.py
```

### 5. Start Development Server

```bash
./scripts/deploy.sh development
```

---

## AI Chat Endpoints

### Enhanced Chat with Context
- `POST /api/chat` - Smart automotive chat with diagnostic context
- `GET /api/chat/stats` - Classification system performance metrics

### Original Chat (A/B Testing)
- `POST /api/ask` - Original automotive chat endpoint

### Chat Features
- **Hybrid Classification**: 95% instant responses, 5% LLM calls
- **Context-Aware**: Integrates VIN, DTC codes, vehicle info
- **Markdown Responses**: Rich formatted diagnostic advice
- **A/B Testing**: Compare original vs enhanced chat performance

---

## OBD2 Scanner API Endpoints

### Scanner Connection
- `GET /api/scanner/ports` - List available serial ports
- `POST /api/scanner/connect` - Connect to OBD2 scanner
- `POST /api/scanner/disconnect` - Disconnect from scanner
- `GET /api/scanner/status` - Get scanner status

### Sensor Data
- `POST /api/scanner/sensors` - Get sensor data (RPM, temperature, speed, etc.)
- `GET /api/scanner/dtc` - Get Diagnostic Trouble Codes
- `GET /api/scanner/vehicle-info` - Get vehicle information (VIN, calibration IDs)

### Manual Data Input
- `POST /api/scanner/manual-data` - Process manually entered OBD2 data

### Scan Sessions
- `POST /api/scanner/scan-session` - Start comprehensive scan session
- `GET /api/scanner/scan-session/{session_id}` - Get scan session results

---

## Authentication & Token Protection

### Get VIN 

```bash
curl -X GET 'http://0.0.0.0:8080/api/manual?vin=3KPF54AD1PE517099'
```

### Connect to OBD2 Scanner

```bash
curl -X POST 'http://0.0.0.0:8080/api/scanner/connect' \
  -H 'Content-Type: application/json' \
  -d '{"port": "/dev/tty.usbserial-0001", "baudrate": 38400}'
```

### Get Sensor Data

```bash
curl -X POST 'http://0.0.0.0:8080/api/scanner/sensors' \
  -H 'Content-Type: application/json' \
  -d '{"pids": ["0105", "010C", "010D"]}'
```

### Process Manual Data

```bash
curl -X POST 'http://0.0.0.0:8080/api/scanner/manual-data' \
  -H 'Content-Type: application/json' \
  -d '{
    "vin": "3KPF54AD1PE517099",
    "dtc_codes": ["P0300", "P0171"],
    "sensor_data": {"engine_temp": 85, "rpm": 2500},
    "notes": "Engine running rough"
  }'
```

---

## Flutter UI

- **LoginSignUpPage**: Toggle between login & signup
- **HomePage**: Navigation buttons (Chat, Docs, Logout)
- **ChatPage**: Chat with RAG or LLM using token

### Flutter Features

- Clean & consistent UI design
- OBD2 scanner integration
- Real-time sensor data display
- DTC code interpretation

---

## API Docs

- Swagger UI → [http://192.168.1.48:8080/docs](http://192.168.1.48:8080/docs)
- Redoc → [http://192.168.1.48:8080/redoc](http://192.168.1.48:8080/redoc)

---

## Supported OBD2 PIDs

| PID | Description | Unit |
|-----|-------------|------|
| 0105 | Engine Coolant Temperature | °C |
| 010C | Engine RPM | RPM |
| 010D | Vehicle Speed | km/h |
| 010F | Intake Air Temperature | °C |
| 0111 | Throttle Position | % |

---

**Ignore in `.gitignore`:**

```gitignore
.venv/
__pycache__/
.env
```

# App Projet OBD2 Scanner Backend

A local AI-powered help desk agent using:

- **FastAPI** for backend
- **Flutter** (mobile/web) UI
- **ELM327** OBD2 scanner support

---

## Setup Instructions (Mac)

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Start FastAPI Server

```bash
python main.py
```

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

- Swagger UI → [http://localhost:8080/docs](http://localhost:8080/docs)
- Redoc → [http://localhost:8080/redoc](http://localhost:8080/redoc)

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

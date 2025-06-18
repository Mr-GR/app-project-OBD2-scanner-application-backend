# App Projet OBD2 Scanner Backend

A local AI-powered help desk agent using:

- **FastAPI** for backend
- **Flutter** (mobile/web) UI

---

## Setup Instructions (Mac)

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv
```

### 2. Start FastAPI Server

```bash
python main.py
```

---

## Authentication & Token Protection


### Get VIN 

```bash
curl -X GET 'http://0.0.0.0:8080/manual?vin=3KPF54AD1PE517099' \
```

---

## Flutter UI

- **LoginSignUpPage**: Toggle between login & signup
- **HomePage**: Navigation buttons (Chat, Docs, Logout)
- **ChatPage**: Chat with RAG or LLM using token

### Flutter Features

- Clean & consistent UI design

---

## API Docs

- Swagger UI → [http://localhost:8080/docs](http://localhost:8080/docs)
- Redoc → [http://localhost:8080/redoc](http://localhost:8080/redoc)

---

**Ignore in `.gitignore`:**

```gitignore
.venv/
__pycache__/
.env
```

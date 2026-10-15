# 🌾 SmartAgro v3 — AI Farm Intelligence & IoT Automation

SmartAgro is an end-to-end intelligent precision agriculture platform. It combines IoT sensor monitoring, Machine Learning for crop recommendation and plant disease diagnosis, and a modern dashboard to help farmers and agronomists optimize farm yields and prevent crop loss.

---

## 🚀 Key Features

- **📡 Real-Time IoT Telemetry**: Continuous monitoring of ambient temperature, humidity, soil moisture, motion detection (PIR), and fire hazard alerts via ESP32.
- **🌱 Intelligent Crop Recommendation**: Random Forest classifier that recommends optimal crops based on N, P, K, temperature, humidity, soil pH, and rainfall (supports soil health card parsing via PDF/document upload).
- **🔬 Leaf Disease Detection**: Deep Learning CNN trained on the PlantVillage dataset for rapid plant pathogen diagnosis directly from uploaded leaf photos (with realistic fallback demo mode).
- **🚨 Autonomous Farm Alerts**: Automated buzzer triggers and live dashboard alerts for intrusion detection and fire risks.
- **🔐 Secure Multi-User Auth**: JWT-authenticated REST APIs with role-ready account registration and management.

---

## 🛠️ Tech Stack & Architecture

- **Backend**: Python 3.10+, Flask, SQLite, Scikit-learn, TensorFlow / Keras, Docling / LlamaParse
- **Frontend**: React.js, Tailwind CSS / Vanilla CSS, Chart.js / Recharts
- **Embedded / Hardware**: ESP32 Dev Module, DHT11, PIR Sensor, Flame Sensor, Capacitive/Resistive Soil Sensor, Active Buzzer (C++ / Arduino)

---

## 📋 Prerequisites

Before starting, ensure you have the following installed on your machine:

- **Python**: `3.9` to `3.11` (TensorFlow compatible)
- **Node.js**: `v16.x` or later & `npm`
- **Git**
- *(Optional for Hardware)*: **Arduino IDE 2.x** with the ESP32 Board Core installed.

---

## ⚡ Quick Start

### Windows
1. Double-click **`start.bat`** (or run `.\start.bat` in PowerShell/CMD).
2. Open your browser and go to: **[http://localhost:3000](http://localhost:3000)**

### Linux / macOS
```bash
chmod +x start.sh
./start.sh
```
Open **[http://localhost:3000](http://localhost:3000)** once the terminal indicates both servers are live.

---

## 💻 Manual Setup

If you prefer to start backend and frontend services individually:

### 1. Backend Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) For high-accuracy PDF soil card parsing:
pip install docling

# (Optional) For CNN leaf disease detection:
pip install tensorflow pillow

# Copy environment configuration
cp .env.example .env

# Start Flask server (runs on http://localhost:5000)
python app.py
```

### 2. Frontend Setup

```bash
cd frontend

# Copy environment configuration
cp .env.example .env

# Install dependencies and start development server
npm install
npm start
```
The application will launch at **[http://localhost:3000](http://localhost:3000)**.

---

## 🧠 Machine Learning Models

### 1. Crop Recommendation (Auto-trains)
The system uses a Random Forest classifier for multi-parameter crop suggestions.
1. Download `Crop_recommendation.csv` from [Kaggle - Crop Recommendation Dataset](https://www.kaggle.com/datasets/atharvaingle/crop-recommendation-dataset).
2. Place `Crop_recommendation.csv` into the `backend/` directory.
3. Start or restart `app.py` — it automatically trains and saves `crop_rf.pkl` and `crop_le.pkl` in ~30 seconds.

### 2. Plant Disease Detection CNN (Manual Training)
1. Download the PlantVillage dataset from [Kaggle - PlantVillage Dataset](https://www.kaggle.com/datasets/emmarex/plantdisease).
2. Extract the color images into `backend/plantvillage/color/`.
3. Train the model:
   ```bash
   cd backend
   python scripts/split_dataset.py   # Splits data into train/ and val/ sets
   python train_cnn.py               # Trains the CNN model (~30-60 min on GPU)
   ```
4. Copy the resulting `plant_disease_cnn.h5` and `class_indices.json` into the `backend/` root directory and restart `app.py`.

> **Note:** If `plant_disease_cnn.h5` is not present, the disease detection module runs seamlessly in **Demo Mode**, inferring realistic diagnostic results without throwing errors.

---

## 📡 Hardware & ESP32 Configuration

### Circuit Connections
| Sensor / Peripheral | ESP32 GPIO Pin | Type / Description |
| :--- | :--- | :--- |
| **DHT11 (Temp & Humidity)** | **GPIO 4** (D4) | Digital 1-Wire |
| **PIR Motion Sensor** | **GPIO 13** (D13) | Digital Input |
| **Flame Sensor** | **GPIO 14** (D14) | Digital / Analog Input |
| **Soil Moisture Sensor** | **GPIO 34** (D34) | Analog ADC Input |
| **Active Buzzer** | **GPIO 25** (D25) | Digital Output |

### Required Arduino Libraries
Install these via the **Arduino Library Manager**:
- `DHT sensor library` by Adafruit
- `Adafruit Unified Sensor`
- `ArduinoJson` (v6 or v7)

### Firmware Setup
1. Open `backend/smart_agro_esp32/smart_agro_esp32.ino` in Arduino IDE.
2. Update the network credentials and your computer's local IP address:
   ```cpp
   #define WIFI_SSID     "YOUR_WIFI_SSID"
   #define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
   #define SERVER_URL    "http://YOUR_PC_IP:5000/api/sensor"
   ```
   *(To find your local IP: Windows `ipconfig` | Linux/Mac `ip addr` or `ifconfig`)*
3. Select board **ESP32 Dev Module**, choose the correct COM port, and click **Upload**.

---

## 🔌 API Reference

### Public Endpoints (No Auth Required)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/ping` | Health check probe |
| `GET` | `/api/status` | Model and system status |
| `POST` | `/api/auth/register` | Register new user (`{username, password, email, name}`) |
| `POST` | `/api/auth/login` | Authenticate and obtain JWT token |
| `POST` | `/api/sensor` | ESP32 telemetry ingestion endpoint |
| `GET` | `/api/sensor` | Fetch latest sensor telemetry payload |
| `GET` | `/sensors/all` | Snapshot of all connected sensors |
| `GET` | `/sensors/<sensor_name>` | Read individual sensor state (`dht11`, `pir`, `flame`, `soil`, `buzzer`) |

### Protected Endpoints (Requires `Authorization: Bearer <TOKEN>`)
| Method | Endpoint | Payload / Params | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/auth/me` | None | Returns profile of authenticated user |
| `POST` | `/api/auth/logout` | None | Invalidates user session |
| `POST` | `/api/recommend` | JSON / multipart (`document`) | Returns crop recommendations based on soil NPK/weather |
| `POST` | `/api/disease` | multipart (`image`) | Returns leaf disease classification and cure remedies |

---

## 📂 Project Structure

```text
smartagro/
├── backend/
│   ├── app.py                      # Flask REST API server
│   ├── database.py                 # SQLite schema & DB utility functions
│   ├── requirements.txt            # Python dependencies
│   ├── train_cnn.py                # CNN training script
│   ├── .env.example                # Sample backend environment config
│   ├── smart_agro_esp32/
│   │   └── smart_agro_esp32.ino    # ESP32 firmware sketch
│   └── scripts/
│       └── split_dataset.py        # Dataset partition utility
├── frontend/
│   ├── package.json                # React packages & scripts
│   ├── .env.example                # Sample frontend environment config
│   ├── public/                     # Static HTML & assets
│   └── src/                        # React components, pages & styles
├── start.bat                       # Windows 1-click startup script
├── start.sh                        # Linux/macOS startup script
└── README.md
```

---

## 🛡️ License

This project is licensed under the [MIT License](LICENSE).

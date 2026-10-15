"""
SmartAgro Backend v3.1 — SQLite Edition
========================================
WHAT'S NEW vs v3.0:
  • All farmer data now persisted in SQLite (smartagro.db)
  • Login sessions survive server restarts
  • Sensor history stored in DB (not lost on restart)
  • Crop recommendations saved per farmer
  • Disease detections logged per farmer
  • New API endpoints:
      GET /api/auth/history/recommendations  — farmer's recommendation history
      GET /api/auth/history/disease          — farmer's disease scan history
      GET /api/auth/stats                    — farmer's aggregated stats
      GET /api/alerts/history                — recent field alerts log
      PUT /api/auth/profile                  — update farm profile

ESP32 Hardware (exact pins):
  DHT11  → GPIO 4    PIR    → GPIO 13
  Flame  → GPIO 14   Soil   → GPIO 34 (ADC)   Buzzer → GPIO 25
       
Run:
  pip install flask flask-cors numpy pillow scikit-learn pandas joblib pdfminer.six pypdf python-docx httpx requests
  python app.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import os, io, time, logging, json, re, random, hashlib, base64
from datetime import datetime, timedelta
from functools import wraps

# ── Import SQLite persistence layer ──────────────────────────────────────────
from database import db

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SECRET = os.environ.get("JWT_SECRET", "smartagro_v3_secret_key_2024")

# ════════════════════════════════════════════════════════════════════════════
#  IN-MEMORY SENSOR CACHE  (DB is the source of truth; this is for speed)
# ════════════════════════════════════════════════════════════════════════════
sensor_store = {
    "temperature": 28.0, "humidity": 65.0, "soil_moisture": 45,
    "pir_motion": False, "flame_detected": False,
    "light_intensity": 720, "co2_ppm": 412, "timestamp": 0,
}

_hw = {
    "temperature": 28.0, "humidity": 65.0, "soil_raw": 3600,
    "soil_moisture_pct": 45, "pir": 0, "flame": 0,
    "timestamp": 0, "source": "simulated",
}

# ════════════════════════════════════════════════════════════════════════════
#  AUTH  — now backed by SQLite
# ════════════════════════════════════════════════════════════════════════════

def hash_pw(password: str) -> str:
    return hashlib.sha256((password + SECRET).encode()).hexdigest()

def make_token(username: str) -> str:
    raw   = f"{username}:{time.time()}:{random.randint(0, 999999)}"
    token = base64.urlsafe_b64encode(
        hashlib.sha256((raw + SECRET).encode()).digest()
    ).decode().rstrip("=")
    expires = datetime.utcnow() + timedelta(hours=48)
    # ── Persist token to SQLite ─────────────────────────────────────
    db.save_token(token, username, expires.isoformat())
    app.logger.info(f"Token created for {username}, expires {expires.isoformat()}")
    return token

def verify_token(token: str) -> str | None:
    """Verify against SQLite — sessions survive server restart."""
    if not token:
        return None
    return db.get_token(token)   # returns username or None

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth  = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip() if auth.startswith("Bearer ") else ""
        username = verify_token(token)
        if not username:
            return jsonify({"error": "Invalid or expired token. Please log in again."}), 401
        request.username = username
        request.token    = token
        return f(*args, **kwargs)
    return decorated

# ════════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/auth/register", methods=["POST"])
def register():
    data     = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password =  data.get("password") or ""
    email    = (data.get("email")    or "").strip()
    name     = (data.get("name")     or username).strip()

    if not username or not password or not email:
        return jsonify({"error": "Username, email and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    # Check duplicates against DB
    if db.get_farmer(username):
        return jsonify({"error": "Username already taken"}), 409
    if db.get_farmer_by_email(email):
        return jsonify({"error": "Email already registered"}), 409

    saved = db.save_farmer(
        username=username,
        password_hash=hash_pw(password),
        email=email,
        full_name=name,
    )
    if not saved:
        return jsonify({"error": "Registration failed — username or email already exists"}), 409

    token = make_token(username)
    return jsonify({"token": token, "username": username, "name": name, "message": "Registered!"}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data     = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password =  data.get("password") or ""

    farmer = db.get_farmer(username)
    if not farmer or farmer["password_hash"] != hash_pw(password):
        return jsonify({"error": "Invalid username or password"}), 401

    db.update_last_login(username)
    token = make_token(username)
    return jsonify({
        "token":    token,
        "username": username,
        "name":     farmer["full_name"],
        "message":  "Login successful!",
    })


@app.route("/api/auth/me", methods=["GET"])
@require_auth
def me():
    farmer = db.get_farmer(request.username)
    if not farmer:
        return jsonify({"error": "Farmer not found"}), 404
    return jsonify({
        "username":        farmer["username"],
        "name":            farmer["full_name"],
        "email":           farmer["email"],
        "phone":           farmer.get("phone", ""),
        "farm_location":   farmer.get("farm_location", ""),
        "farm_size_acres": farmer.get("farm_size_acres", 0),
        "created_at":      farmer.get("created_at"),
        "last_login_at":   farmer.get("last_login_at"),
    })


@app.route("/api/auth/profile", methods=["PUT"])
@require_auth
def update_profile():
    data = request.get_json(force=True, silent=True) or {}
    allowed_fields = {}
    if "name" in data:             allowed_fields["full_name"]       = str(data["name"]).strip()
    if "phone" in data:            allowed_fields["phone"]           = str(data["phone"]).strip()
    if "farm_location" in data:    allowed_fields["farm_location"]   = str(data["farm_location"]).strip()
    if "farm_size_acres" in data:
        try:
            allowed_fields["farm_size_acres"] = float(data["farm_size_acres"])
        except (ValueError, TypeError):
            return jsonify({"error": "farm_size_acres must be a number"}), 400
    if not allowed_fields:
        return jsonify({"error": "No valid fields provided"}), 400
    db.update_farmer_profile(request.username, **allowed_fields)
    return jsonify({"message": "Profile updated", "updated_fields": list(allowed_fields.keys())})


@app.route("/api/auth/logout", methods=["POST"])
@require_auth
def logout():
    db.delete_token(request.token)
    return jsonify({"message": "Logged out"})


# ── Farmer history & stats ────────────────────────────────────────────────────

@app.route("/api/auth/history/recommendations", methods=["GET"])
@require_auth
def recommendation_history():
    limit = min(int(request.args.get("limit", 20)), 100)
    recs  = db.get_recommendations(request.username, limit=limit)
    return jsonify({"count": len(recs), "history": recs})


@app.route("/api/auth/history/disease", methods=["GET"])
@require_auth
def disease_history():
    limit = min(int(request.args.get("limit", 20)), 100)
    logs  = db.get_disease_logs(request.username, limit=limit)
    return jsonify({"count": len(logs), "history": logs})


@app.route("/api/auth/stats", methods=["GET"])
@require_auth
def farmer_stats():
    stats = db.get_farmer_stats(request.username)
    return jsonify(stats)


# ════════════════════════════════════════════════════════════════════════════
#  HARDWARE SENSOR FUNCTIONS  (same as v3.0)
# ════════════════════════════════════════════════════════════════════════════

def read_dht11():
    if _hw["source"] != "simulated":
        return _hw["temperature"], _hw["humidity"]
    return round(random.uniform(24.0, 36.0), 1), round(random.uniform(40.0, 80.0), 1)

def read_pir():
    if _hw["source"] != "simulated":
        return int(_hw["pir"])
    return random.choice([0, 0, 0, 1])

def read_flame():
    if _hw["source"] != "simulated":
        return int(_hw["flame"])
    return random.choice([0, 0, 0, 0, 0, 1])

def read_soil():
    if _hw["source"] != "simulated":
        pct = _hw.get("soil_moisture_pct", 50)
        return int(4095 - (pct / 100.0) * (4095 - 3000))
    return random.randint(2800, 4095)

def soil_analysis(raw_value):
    soil_percent = int((4095 - raw_value) / (4095 - 3000) * 100)
    soil_percent = max(0, min(100, soil_percent))
    if raw_value > 3900:   status = "DRY"
    elif raw_value > 3300: status = "MOIST"
    else:                  status = "WET"
    return {"raw": raw_value, "percent": soil_percent, "status": status, "alert": soil_percent < 25}

def buzzer_status(flame_detected, soil_dry=False, temp_high=False):
    if flame_detected:
        return {"active": True,  "frequency_hz": 2000, "reason": "Flame detected!"}
    if temp_high:
        return {"active": True,  "frequency_hz": 1000, "reason": "High temperature warning"}
    if soil_dry:
        return {"active": True,  "frequency_hz": 500,  "reason": "Soil too dry — irrigate!"}
    return     {"active": False, "frequency_hz": 0,    "reason": "No alert"}

# ════════════════════════════════════════════════════════════════════════════
#  SENSOR ROUTES  — readings now also saved to SQLite
# ════════════════════════════════════════════════════════════════════════════

@app.route("/sensors/all", methods=["GET"])
def all_sensors():
    temp, hum = read_dht11()
    pir        = read_pir()
    flame      = read_flame()
    soil_raw   = read_soil()
    soil       = soil_analysis(soil_raw)
    buzzer     = buzzer_status(bool(flame), soil["status"] == "DRY", temp > 38)
    _hw.update({"temperature": temp, "humidity": hum, "pir": pir, "flame": flame, "timestamp": time.time()})
    return jsonify({
        "dht11":  {"temperature_c": temp, "humidity_percent": hum, "error": False},
        "pir":    {"motion_detected": bool(pir), "raw": pir},
        "flame":  {"flame_detected": bool(flame), "raw": flame},
        "soil":   soil,
        "buzzer": buzzer,
        "source": _hw["source"],
        "timestamp": _hw["timestamp"],
    })

@app.route("/sensors/dht11",  methods=["GET"])
def sensor_dht11():
    t, h = read_dht11()
    return jsonify({"temperature_c": t, "humidity_percent": h,
                    "status": "HOT" if t > 35 else "WARM" if t > 28 else "NORMAL"})

@app.route("/sensors/pir",    methods=["GET"])
def sensor_pir():
    s = read_pir()
    return jsonify({"motion_detected": bool(s), "raw": s})

@app.route("/sensors/flame",  methods=["GET"])
def sensor_flame():
    s = read_flame()
    return jsonify({"flame_detected": bool(s), "raw": s, "buzzer": buzzer_status(bool(s))})

@app.route("/sensors/soil",   methods=["GET"])
def sensor_soil():
    return jsonify(soil_analysis(read_soil()))

@app.route("/sensors/buzzer", methods=["GET"])
def sensor_buzzer():
    flame = read_flame()
    soil  = soil_analysis(read_soil())
    t, _  = read_dht11()
    return jsonify(buzzer_status(bool(flame), soil["status"] == "DRY", t > 38))


@app.route("/api/sensor", methods=["POST"])
def receive_sensor():
    """ESP32 posts here every 5 seconds — data saved to SQLite."""
    data = request.get_json(force=True, silent=True) or {}
    reading = {
        "temperature":     float(data.get("temperature",    0)),
        "humidity":        float(data.get("humidity",       0)),
        "soil_moisture":   int(data.get("soil_moisture",    0)),
        "soil_raw":        int(data.get("soil_raw",         0)),
        "pir_motion":      bool(data.get("pir_motion",      False)),
        "flame_detected":  bool(data.get("flame_detected",  False)),
        "light_intensity": int(data.get("light_intensity",  0)),
        "co2_ppm":         int(data.get("co2_ppm",          400)),
        "source":          "esp32",
        "timestamp":       time.time(),
    }

    # Update in-memory cache
    sensor_store.update(reading)
    _hw.update({
        "temperature":       reading["temperature"],
        "humidity":          reading["humidity"],
        "pir":               int(reading["pir_motion"]),
        "flame":             int(reading["flame_detected"]),
        "soil_moisture_pct": reading["soil_moisture"],
        "timestamp":         reading["timestamp"],
        "source":            "esp32",
    })

    # ── Persist to SQLite ───────────────────────────────────────────
    db.save_sensor(reading)

    # Build alerts
    alerts = []
    if reading["soil_moisture"] < 30:
        alerts.append({"type": "LOW_MOISTURE", "severity": "warning",  "message": "Soil moisture critically low"})
        db.save_alert("LOW_MOISTURE", "warning", "Soil moisture critically low", reading)
    if reading["temperature"] > 38:
        alerts.append({"type": "HIGH_TEMP",    "severity": "danger",   "message": "High temperature detected"})
        db.save_alert("HIGH_TEMP", "danger", f"Temperature {reading['temperature']}°C exceeds threshold", reading)
    if reading["flame_detected"]:
        alerts.append({"type": "FLAME",        "severity": "critical", "message": "Fire hazard! Evacuate area."})
        db.save_alert("FLAME", "critical", "Flame sensor triggered — fire hazard!", reading)
    if reading["pir_motion"]:
        alerts.append({"type": "MOTION",       "severity": "info",     "message": "Motion detected in field"})

    return jsonify({"received": True, "alerts": alerts})


@app.route("/api/sensor", methods=["GET"])
def get_sensor():
    """Return live cache + last 20 from DB history."""
    history = db.get_sensor_history(n=20)
    return jsonify({**sensor_store, "history": history})


@app.route("/api/sensor/history", methods=["GET"])
def sensor_history_route():
    """Full sensor history from DB."""
    n    = min(int(request.args.get("n", 50)), 500)
    rows = db.get_sensor_history(n=n)
    return jsonify({"count": len(rows), "history": rows})


@app.route("/api/alerts/history", methods=["GET"])
def alerts_history():
    limit = min(int(request.args.get("limit", 50)), 200)
    logs  = db.get_alert_logs(limit=limit)
    return jsonify({"count": len(logs), "alerts": logs})


# ════════════════════════════════════════════════════════════════════════════
#  ML MODELS  (unchanged from v3.0)
# ════════════════════════════════════════════════════════════════════════════

rf_model   = None
cnn_model  = None
cnn_labels = []

DISEASE_LABELS = [
    "Apple___Apple_scab","Apple___Black_rot","Apple___Cedar_apple_rust","Apple___healthy",
    "Blueberry___healthy","Cherry___Powdery_mildew","Cherry___healthy",
    "Corn___Cercospora_leaf_spot","Corn___Common_rust","Corn___Northern_Leaf_Blight","Corn___healthy",
    "Grape___Black_rot","Grape___Esca","Grape___Leaf_blight","Grape___healthy",
    "Orange___Haunglongbing","Peach___Bacterial_spot","Peach___healthy",
    "Pepper___Bacterial_spot","Pepper___healthy",
    "Potato___Early_blight","Potato___Late_blight","Potato___healthy",
    "Raspberry___healthy","Soybean___healthy","Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch","Strawberry___healthy",
    "Tomato___Bacterial_spot","Tomato___Early_blight","Tomato___Late_blight",
    "Tomato___Leaf_Mold","Tomato___Septoria_leaf_spot","Tomato___Spider_mites",
    "Tomato___Target_Spot","Tomato___Yellow_Leaf_Curl_Virus",
    "Tomato___mosaic_virus","Tomato___healthy",
]

CROP_INFO = {
    "rice":     {"season":"Kharif",    "duration":"120-150 days","water":"High",   "temp":"20-35°C"},
    "maize":    {"season":"Kharif/Rabi","duration":"80-110 days", "water":"Medium", "temp":"18-27°C"},
    "banana":   {"season":"Year-round","duration":"10-12 months","water":"High",   "temp":"20-35°C"},
    "mango":    {"season":"Summer",    "duration":"5-8 years",   "water":"Low-Medium","temp":"24-30°C"},
    "cotton":   {"season":"Kharif",    "duration":"150-180 days","water":"Medium", "temp":"21-30°C"},
    "chickpea": {"season":"Rabi",      "duration":"95-110 days", "water":"Low",    "temp":"20-25°C"},
    "wheat":    {"season":"Rabi",      "duration":"110-130 days","water":"Medium", "temp":"15-25°C"},
    "coffee":   {"season":"Year-round","duration":"3-4 years",   "water":"Medium", "temp":"15-28°C"},
}

TREATMENTS = {
    "Apple___Black_rot":         ["Prune diseased wood","Apply captan fungicide (2g/L)","Remove infected fruit"],
    "Apple___Apple_scab":        ["Apply myclobutanil at petal fall","Rake fallen leaves","Prune for airflow"],
    "Corn___Northern_Leaf_Blight":["Apply propiconazole at VT stage","Use resistant hybrids","Rotate crops"],
    "Corn___Common_rust":        ["Apply azoxystrobin early","Plant early in season","Remove infected tissue"],
    "Grape___Black_rot":         ["Apply mancozeb pre-bloom","Remove mummified fruit","Improve canopy airflow"],
    "Potato___Early_blight":     ["Apply chlorothalonil every 7-10 days","Remove infected leaves","Rotate crops"],
    "Potato___Late_blight":      ["Apply mancozeb immediately","Destroy infected plants","Use certified seed"],
    "Tomato___Early_blight":     ["Remove infected leaves","Apply copper fungicide weekly","Mulch around base"],
    "Tomato___Late_blight":      ["Apply copper spray every 5-7 days","Avoid overhead irrigation","Remove debris"],
    "Tomato___Bacterial_spot":   ["Apply copper bactericide","Use disease-free seed","Avoid wetting foliage"],
    "Tomato___Leaf_Mold":        ["Improve air circulation","Reduce humidity below 85%","Apply mancozeb"],
    "Orange___Haunglongbing":    ["Remove infected trees immediately","Control psyllid vector","Use certified stock"],
    "Strawberry___Leaf_scorch":  ["Apply captan","Remove infected leaves","Avoid overhead watering"],
    "Squash___Powdery_mildew":   ["Apply sulfur spray","Improve spacing","Use resistant varieties"],
}
DEFAULT_TREAT = ["Monitor closely for 48 hours","Consult local agronomist","Maintain optimal NPK nutrition"]


def _probe_h5_num_classes(model_path: str) -> int:
    """
    Read the final Dense layer output units directly from the .h5 file
    WITHOUT loading the model — tells us how many classes were trained.
    """
    try:
        import h5py
        with h5py.File(model_path, "r") as f:
            # Walk all datasets and find the softmax Dense bias (last dense layer)
            shapes = []
            def visitor(name, obj):
                if isinstance(obj, h5py.Dataset) and "bias" in name and "dense" in name.lower():
                    shapes.append((name, obj.shape))
            f.visititems(visitor)
            if shapes:
                # Last dense bias shape = (num_classes,)
                last = shapes[-1][1]
                if len(last) == 1:
                    return int(last[0])
    except Exception as e:
        app.logger.warning(f"h5 probe failed: {e}")
    return 38  # safe default


def _build_mobilenetv2_model(num_classes: int) -> "tf.keras.Model":
    """
    Rebuild the EXACT Sequential MobileNetV2 architecture from train_cnn.py:
      MobileNetV2(224x224, include_top=False)
      → GlobalAveragePooling2D
      → BatchNormalization
      → Dense(512, relu, l2)
      → Dropout(0.4)
      → Dense(256, relu, l2)
      → Dropout(0.3)
      → Dense(num_classes, softmax)

    Input images must be pre-normalised to [0, 1] before passing in.
    MobileNetV2 was trained with ImageNet weights and rescale=1./255 in the
    data generator — so [0,1] float input is correct here.
    """
    import tensorflow as tf
    from tensorflow.keras.applications import MobileNetV2
    from tensorflow.keras import layers, models, regularizers

    base = MobileNetV2(
        input_shape=(224, 224, 3),
        include_top=False,
        weights=None,           # weights loaded from .h5 separately
    )
    model = models.Sequential([
        base,
        layers.GlobalAveragePooling2D(),
        layers.BatchNormalization(),
        layers.Dense(512, activation="relu",
                     kernel_regularizer=regularizers.l2(1e-4)),
        layers.Dropout(0.4),
        layers.Dense(256, activation="relu",
                     kernel_regularizer=regularizers.l2(1e-4)),
        layers.Dropout(0.3),
        layers.Dense(num_classes, activation="softmax"),
    ])
    # Build the model so weight shapes are concrete
    model.build((None, 224, 224, 3))
    return model



# ════════════════════════════════════════════════════════════════════════════
#  SIMPLE & CORRECT CNN LOADER
# ════════════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════════
#  SAFE CNN LOADER (WORKS WITH OLD .H5 MODELS)
# ════════════════════════════════════════════════════════════════════════
def _load_cnn_model(model_path: str):

    try:
        import tensorflow as tf

        # Create a SafeDense layer to ignore the problematic quantization_config parameter
        # which breaks when loading some legacy Keras 3 models into Keras 3.12+
        SafeDense = type(
            'SafeDense',
            (tf.keras.layers.Dense,),
            {
                'from_config': classmethod(
                    lambda cls, config: super(cls, cls).from_config(
                        {k: v for k, v in config.items() if k != 'quantization_config'}
                    )
                )
            }
        )

        # Directly load full model
        model = tf.keras.models.load_model(
            model_path,
            custom_objects={'Dense': SafeDense}
        )

        model.compile(
            optimizer="adam",
            loss="categorical_crossentropy",
            metrics=["accuracy"]
        )

        app.logger.info("CNN model loaded successfully ✓")

        return model

    except Exception as e:

        app.logger.error(
            f"CNN load failed: {e}",
            exc_info=True
        )

        return None

# ════════════════════════════════════════════════════════════════════════════
#  LOAD MODELS
# ════════════════════════════════════════════════════════════════════════════

def load_models():
    global rf_model, cnn_model, cnn_labels

    # ─────────────────────────────────────────────────────────────
    # Random Forest Crop Recommendation Model
    # ─────────────────────────────────────────────────────────────

    csv_path = "Crop_recommendation.csv"

    if os.path.exists(csv_path):
        try:
            import pandas as pd
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import LabelEncoder
            from sklearn.model_selection import train_test_split
            import joblib

            df = pd.read_csv(csv_path)

            le = LabelEncoder()
            df["le"] = le.fit_transform(df["label"])

            X = df[
                ["N", "P", "K", "temperature",
                 "humidity", "ph", "rainfall"]
            ].values

            y = df["le"].values

            Xtr, Xte, ytr, yte = train_test_split(
                X, y,
                test_size=0.2,
                random_state=42
            )

            clf = RandomForestClassifier(
                n_estimators=200,
                random_state=42,
                class_weight="balanced"
            )

            clf.fit(Xtr, ytr)

            acc = clf.score(Xte, yte)

            app.logger.info(f"RF accuracy: {acc:.4f}")

            joblib.dump(clf, "crop_rf.pkl")
            joblib.dump(le, "crop_le.pkl")

            rf_model = (clf, le)

        except Exception as e:
            app.logger.warning(f"RF train failed: {e}")

    else:
        try:
            import joblib

            clf = joblib.load("crop_rf.pkl")
            le  = joblib.load("crop_le.pkl")

            rf_model = (clf, le)

            app.logger.info("Loaded pre-trained RF model")

        except Exception:
            app.logger.warning(
                "No RF model found — using rule-based fallback"
            )

    # ─────────────────────────────────────────────────────────────
    # CNN Disease Detection Model
    # ─────────────────────────────────────────────────────────────

    model_path = "plant_disease_cnn.h5"

    if os.path.exists(model_path):

        cnn_model = _load_cnn_model(model_path)

        if cnn_model is not None:

            # Load class labels
            if os.path.exists("class_indices.json"):

                with open("class_indices.json", "r") as f:
                    idx_map = json.load(f)

                cnn_labels = [
                    k for k, v in sorted(
                        idx_map.items(),
                        key=lambda x: x[1]
                    )
                ]

            else:
                cnn_labels = DISEASE_LABELS

            # Validate label count
            try:
                model_out = cnn_model.output_shape[-1]

                if model_out != len(cnn_labels):

                    app.logger.warning(
                        f"Label mismatch! "
                        f"Model output={model_out} "
                        f"but labels={len(cnn_labels)}"
                    )

                    if model_out < len(cnn_labels):
                        cnn_labels = cnn_labels[:model_out]

            except Exception:
                pass

            app.logger.info(
                f"CNN ready — "
                f"{len(cnn_labels)} classes, "
                f"input={cnn_model.input_shape}"
            )

        else:
            app.logger.error(
                "CNN model successfully loaded."
            )

    else:
        app.logger.warning(
            "plant_disease_cnn.h5 not found — "
            "disease detection in demo mode"
        )
# ════════════════════════════════════════════════════════════════════════════
#  DOCUMENT PARSING  (unchanged from v3.0)
# ════════════════════════════════════════════════════════════════════════════

def extract_params(text):
    params = {}
    pats = {
        "N":  [r"nitrogen[:\s]+(\d+\.?\d*)",r"\bN[:\s]+(\d+\.?\d*)",r"N\s*=\s*(\d+\.?\d*)"],
        "P":  [r"phosphorus[:\s]+(\d+\.?\d*)",r"\bP[:\s]+(\d+\.?\d*)",r"P\s*=\s*(\d+\.?\d*)"],
        "K":  [r"potassium[:\s]+(\d+\.?\d*)",r"\bK[:\s]+(\d+\.?\d*)",r"K\s*=\s*(\d+\.?\d*)"],
        "ph": [r"ph[:\s]+(\d+\.?\d*)",r"pH\s*=\s*(\d+\.?\d*)"],
        "temperature": [r"temp(?:erature)?[:\s]+(\d+\.?\d*)"],
        "humidity":    [r"humidity[:\s]+(\d+\.?\d*)"],
        "rainfall":    [r"rain(?:fall)?[:\s]+(\d+\.?\d*)",r"precipitation[:\s]+(\d+\.?\d*)"],
    }
    tl = text.lower()
    for param, ps in pats.items():
        for p in ps:
            m = re.search(p, tl)
            if m: params[param] = float(m.group(1)); break
    return params


def parse_document(file_bytes, filename):
    fname = filename.lower()
    key = os.environ.get("LLAMA_CLOUD_API_KEY", "")
    if key:
        try:
            import httpx
            r = httpx.post("https://api.cloud.llamaindex.ai/api/parsing/upload",
                           files={"file": (filename, file_bytes)},
                           headers={"Authorization": f"Bearer {key}"}, timeout=30)
            if r.status_code == 200:
                jid = r.json().get("id")
                for _ in range(10):
                    time.sleep(3)
                    pr = httpx.get(f"https://api.cloud.llamaindex.ai/api/parsing/job/{jid}/result/text",
                                   headers={"Authorization": f"Bearer {key}"}, timeout=15)
                    if pr.status_code == 200: return pr.json().get("text", ""), "LlamaParse"
        except Exception: pass
    try:
        from docling.document_converter import DocumentConverter
        import tempfile
        ext = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_bytes); tp = tmp.name
        r = DocumentConverter().convert(tp); os.unlink(tp)
        return r.document.export_to_markdown(), "Docling"
    except Exception: pass
    if fname.endswith(".pdf"):
        try:
            from pdfminer.high_level import extract_text
            return extract_text(io.BytesIO(file_bytes)), "pdfminer"
        except Exception: pass
        try:
            from pypdf import PdfReader
            r = PdfReader(io.BytesIO(file_bytes))
            return "\n".join(p.extract_text() or "" for p in r.pages), "pypdf"
        except Exception: pass
    if fname.endswith(".docx"):
        try:
            from docx import Document
            return "\n".join(p.text for p in Document(io.BytesIO(file_bytes)).paragraphs), "python-docx"
        except Exception: pass
    if fname.endswith((".txt", ".csv")):
        return file_bytes.decode("utf-8", errors="ignore"), "plain-text"
    return None, None


# ════════════════════════════════════════════════════════════════════════════
#  CROP RECOMMENDATION  — now saves to SQLite
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/recommend", methods=["POST"])
@require_auth
def recommend():
    doc_parsed = False; parse_method = None; raw = {}

    if request.files.get("document"):
        f = request.files["document"]
        text, parse_method = parse_document(f.read(), f.filename or "doc.pdf")
        if text:
            raw = extract_params(text); doc_parsed = True
        else:
            return jsonify({"error": "Could not parse document. Try PDF, DOCX, or TXT."}), 400

    body = {}
    ct = request.content_type or ""
    if "application/json" in ct:
        body = request.get_json(force=True, silent=True) or {}
    elif request.form:
        body = dict(request.form)
    for k in ["N","P","K","ph","temperature","humidity","rainfall"]:
        if k in body:
            try: raw[k] = float(body[k])
            except Exception: pass

    defs = {
        "N": 60.0, "P": 40.0, "K": 40.0, "ph": 6.5,
        "temperature": sensor_store.get("temperature") or 25.0,
        "humidity":    sensor_store.get("humidity")    or 65.0,
        "rainfall":    100.0,
    }
    for k, v in defs.items():
        if k not in raw: raw[k] = v

    try:
        feat = np.array([[float(raw[k]) for k in ["N","P","K","temperature","humidity","ph","rainfall"]]])
    except Exception as e:
        return jsonify({"error": f"Invalid parameter: {e}"}), 400

    if rf_model:
        clf, le = rf_model
        proba   = clf.predict_proba(feat)[0]
        top3    = np.argsort(proba)[-3:][::-1]
        recs    = [{"crop": le.inverse_transform([i])[0],
                    "confidence": round(float(proba[i]) * 100, 1),
                    "info": CROP_INFO.get(le.inverse_transform([i])[0], {})} for i in top3]
    else:
        n, p, k, ph, t = raw["N"], raw["P"], raw["K"], raw["ph"], raw["temperature"]
        if ph < 5.5:          candidates = [("rice",82), ("coffee",70)]
        elif n > 80:          candidates = [("rice",86), ("maize",74), ("jute",62)]
        elif p > 60 and k>60: candidates = [("banana",80), ("mango",68), ("papaya",60)]
        elif n < 40:          candidates = [("chickpea",78), ("lentil",71)]
        elif t < 20:          candidates = [("wheat",80), ("lentil",72), ("chickpea",65)]
        else:                 candidates = [("maize",74), ("cotton",65), ("mungbean",58)]
        recs = [{"crop": c, "confidence": conf, "info": CROP_INFO.get(c, {})} for c, conf in candidates]

    nv, pv, kv, phv = raw["N"], raw["P"], raw["K"], raw["ph"]
    fert = [
        {"nutrient":"Nitrogen",   "status":"deficient" if nv<40 else "excess" if nv>100 else "optimal",
         "advice":"Apply Urea 60 kg/ha" if nv<40 else "Reduce N fertilizer" if nv>100 else "N level is adequate"},
        {"nutrient":"Phosphorus", "status":"deficient" if pv<30 else "excess" if pv>80 else "optimal",
         "advice":"Apply DAP 40 kg/ha" if pv<30 else "Excess P — monitor zinc" if pv>80 else "P level is adequate"},
        {"nutrient":"Potassium",  "status":"deficient" if kv<40 else "excess" if kv>100 else "optimal",
         "advice":"Apply MOP 30 kg/ha" if kv<40 else "Avoid additional K" if kv>100 else "K level is adequate"},
    ]
    ph_advice = ("Acidic soil — apply lime 2-3 t/ha" if phv < 6.0
                 else "Alkaline soil — apply sulfur/gypsum" if phv > 7.5
                 else "pH is in optimal range (6.0–7.5)")

    # ── Save to SQLite ─────────────────────────────────────────────
    db.save_recommendation(
        username=request.username,
        params=raw,
        results=recs,
        fertilizer_tips=fert,
        parse_method=parse_method,
    )

    return jsonify({
        "recommendations":  recs,
        "fertilizer_tips":  fert,
        "ph_advice":        ph_advice,
        "extracted_params": {k: raw[k] for k in ["N","P","K","ph","temperature","humidity","rainfall"]},
        "document_parsed":  doc_parsed,
        "parse_method":     parse_method,
    })


# ════════════════════════════════════════════════════════════════════════════
#  DISEASE DETECTION  — now saves to SQLite
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/disease", methods=["POST"])
@require_auth
def detect_disease():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded. Please select a leaf image."}), 400

    img_file   = request.files["image"]
    img_bytes  = img_file.read()
    image_name = img_file.filename or "leaf.jpg"
    labels     = cnn_labels if cnn_labels else DISEASE_LABELS

    # ── Demo mode ──────────────────────────────────────────────────
    if not cnn_model:
        fname = image_name.lower()
        if   "corn"   in fname or "maize"  in fname: mock = "Corn___Common_rust"
        elif "tomato" in fname:                       mock = "Tomato___Early_blight"
        elif "potato" in fname:                       mock = "Potato___Late_blight"
        elif "apple"  in fname:                       mock = "Apple___Apple_scab"
        elif "grape"  in fname:                       mock = "Grape___Black_rot"
        else:                                         mock = "Tomato___healthy"
        is_healthy = "healthy" in mock.lower()
        result = {
            "disease":    mock.replace("___", " — ").replace("_", " "),
            "raw_label":  mock,
            "confidence": 78.4,
            "severity":   "Healthy" if is_healthy else "Moderate",
            "is_healthy": is_healthy,
            "treatments": [] if is_healthy else TREATMENTS.get(mock, DEFAULT_TREAT),
            "top5":       [{"label": mock.replace("___"," — ").replace("_"," "), "confidence": 78.4}],
            "demo_mode":  True,
            "note":       "CNN model not loaded. Place plant_disease_cnn.h5 in backend folder.",
        }
        # ── Save to SQLite ─────────────────────────────────────────
        db.save_disease_log(
            username=request.username,
            disease_label=mock,
            disease_display=result["disease"],
            confidence=78.4,
            severity=result["severity"],
            is_healthy=is_healthy,
            treatments=result["treatments"],
            image_filename=image_name,
            demo_mode=True,
        )
        return jsonify(result)

    # ── Real CNN inference ──────────────────────────────────────────
    try:
        from PIL import Image as PILImage

        # ── Resolve image size — MobileNetV2 needs 224×224 ──────────
        # Try to read from model, fall back to 224 (MobileNetV2 native size)
        try:
            inp_shape = cnn_model.input_shape  # (None, H, W, 3)
            h = int(inp_shape[1]) if (inp_shape[1] and inp_shape[1] > 32) else 224
            w = int(inp_shape[2]) if (inp_shape[2] and inp_shape[2] > 32) else 224
        except Exception:
            h, w = 224, 224

        # ── Preprocess: match train_cnn.py exactly ──────────────────
        # train_cnn.py used ImageDataGenerator(rescale=1./255)
        # → images are in [0, 1] float range going into MobileNetV2
        # DO NOT apply tf.keras.applications.mobilenet_v2.preprocess_input
        # (that expects [-1,1]) — our training used simple /255 rescaling
        img = PILImage.open(io.BytesIO(img_bytes)).resize((w, h)).convert("RGB")
        arr = np.array(img, dtype=np.float32) / 255.0   # [0, 1] — matches training
        arr = np.expand_dims(arr, axis=0)                # (1, 224, 224, 3)

        # ── Predict ─────────────────────────────────────────────────
        raw_preds = np.array(cnn_model.predict(arr, verbose=0)[0], dtype=np.float64)
        raw_preds = np.clip(raw_preds, 1e-10, 1.0)

        # Raw softmax probability — use directly (no temperature scaling)
        # Temperature scaling was causing false low-confidence on good images
        preds      = raw_preds / raw_preds.sum()
        top_idx    = int(np.argmax(preds))
        confidence = float(preds[top_idx]) * 100

        app.logger.info(
            f"Inference: top={top_idx} conf={confidence:.1f}% "
            f"input_shape=({h},{w}) labels_count={len(labels)}"
        )

        # ── Low-confidence guard — threshold 15% (MobileNetV2 is well-calibrated)
        # Only trigger if ALL classes are near-uniform (true uncertainty)
        # A 20% confidence over 38 classes is actually significant (random = 2.6%)
        entropy    = -np.sum(preds * np.log(preds + 1e-10))
        max_entropy = np.log(len(preds))  # worst-case uniform distribution
        normalised_entropy = entropy / max_entropy   # 0 = certain, 1 = random

        if confidence < 15 or normalised_entropy > 0.95:
            return jsonify({
                "disease":    "Uncertain — Image Not Clear Enough",
                "confidence": round(confidence, 2),
                "severity":   "Unknown",
                "message":    "Confidence too low. Tips: shoot in natural daylight, fill the frame with the leaf, avoid blur.",
                "treatments": [
                    "Retake the photo in bright natural light",
                    "Make sure the leaf fills most of the frame",
                    "Avoid shadows and blurry images",
                    "Consult your local agricultural extension officer",
                ],
                "top5":       [],
                "is_healthy": False,
                "demo_mode":  False,
            })

        # ── Map prediction to label & metadata ──────────────────────
        label      = labels[top_idx] if top_idx < len(labels) else f"class_{top_idx}"
        is_healthy = "healthy" in label.lower()

        sev_map = {
            "scab":       "Moderate",
            "rot":        "Severe",
            "blight":     "Severe",
            "rust":       "Moderate",
            "mildew":     "Moderate",
            "spot":       "Moderate",
            "virus":      "Severe",
            "greening":   "Critical",
            "measles":    "Severe",
            "mosaic":     "Severe",
            "curl":       "Severe",
            "scorch":     "Moderate",
        }
        severity = "Healthy" if is_healthy else next(
            (v for k, v in sev_map.items() if k in label.lower()), "Moderate"
        )

        # ── Top-5 breakdown ─────────────────────────────────────────
        top5 = [
            {
                "label": (
                    labels[i].replace("___", " — ").replace("_", " ")
                    if i < len(labels) else f"class_{i}"
                ),
                "confidence": round(float(preds[i]) * 100, 2),
            }
            for i in np.argsort(preds)[-5:][::-1]
        ]

        treatments = [] if is_healthy else TREATMENTS.get(label, DEFAULT_TREAT)

        # ── Persist to SQLite ───────────────────────────────────────
        db.save_disease_log(
            username=request.username,
            disease_label=label,
            disease_display=label.replace("___", " — ").replace("_", " "),
            confidence=round(confidence, 2),
            severity=severity,
            is_healthy=is_healthy,
            treatments=treatments,
            image_filename=image_name,
            demo_mode=False,
        )

        return jsonify({
            "disease":    label.replace("___", " — ").replace("_", " "),
            "raw_label":  label,
            "confidence": round(confidence, 2),
            "severity":   severity,
            "is_healthy": is_healthy,
            "treatments": treatments,
            "top5":       top5,
            "demo_mode":  False,
        })

    except Exception as e:
        app.logger.error(f"CNN inference error: {e}", exc_info=True)
        return jsonify({"error": f"Inference error: {str(e)}"}), 500


# ════════════════════════════════════════════════════════════════════════════
#  STATUS  — now includes DB stats
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/status", methods=["GET"])
def status():
    global_stats = db.get_global_stats()
    return jsonify({
        "status":           "Active",
        "version":          "3.1-sqlite",
        "rf_model":         rf_model  is not None,
        "cnn_model":        cnn_model is not None,
        "cnn_classes":      len(cnn_labels),
        "sensor_source":    _hw["source"],
        "llamaparse_ready": bool(os.environ.get("LLAMA_CLOUD_API_KEY")),
        "database":         global_stats,
    })


@app.route("/",         methods=["GET"])
def root():
    return jsonify({"message": "SmartAgro API v3.1-sqlite", "status": "running"})

@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"pong": True, "time": datetime.utcnow().isoformat()})


# ════════════════════════════════════════════════════════════════════════════
#  STARTUP
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 1. Init SQLite (create tables if not exist)
    db.init()
    # 2. Purge expired tokens from previous runs
    db.purge_expired_tokens()
    # 3. Load ML models
    load_models()

    port = int(os.environ.get("PORT", 5000))
    app.logger.info(f"SmartAgro backend v3.1-sqlite starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)
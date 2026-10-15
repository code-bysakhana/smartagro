"""
database.py — SmartAgro SQLite Persistence Layer
=================================================
Stores ALL farmer data that was previously lost on server restart:
  • farmers         — registered accounts (username, hashed password, profile)
  • auth_tokens     — active login sessions with expiry
  • sensor_readings — ESP32 readings history (rolling, auto-pruned to 1000 rows)
  • recommendations — every crop recommendation result a farmer ran
  • disease_logs    — every disease detection result with image filename

SQLite is built into Python — zero extra installation needed.
Database file: smartagro.db (created automatically in backend/ folder)

Usage (in app.py):
    from database import db
    db.init()                          # call once at startup
    db.save_farmer(...)
    db.get_farmer(username)
    db.save_token(token, username, expires_at)
    db.get_token(token)  → username or None
    db.delete_token(token)
    db.save_sensor(data_dict)
    db.get_sensor_history(n=50)
    db.save_recommendation(username, params, results)
    db.get_recommendations(username, limit=20)
    db.save_disease_log(username, label, confidence, is_healthy, image_filename)
    db.get_disease_logs(username, limit=20)
    db.get_farmer_stats(username)
"""

import sqlite3
import os
import json
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager
from threading import Lock

logger = logging.getLogger(__name__)

# ── Database file path (sits next to app.py in backend/) ─────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "smartagro.db")

# SQLite is not thread-safe for writes by default — use a lock
_write_lock = Lock()


# ════════════════════════════════════════════════════════════════════════════
#  CONNECTION HELPER
# ════════════════════════════════════════════════════════════════════════════

@contextmanager
def _conn():
    """Open a connection with WAL mode (safe for concurrent Flask requests)."""
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row          # rows behave like dicts
    con.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging — better concurrency
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ════════════════════════════════════════════════════════════════════════════
#  SCHEMA
# ════════════════════════════════════════════════════════════════════════════

_SCHEMA = """
-- ── Farmer accounts ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS farmers (
    username        TEXT PRIMARY KEY,
    password_hash   TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    full_name       TEXT NOT NULL,
    phone           TEXT DEFAULT '',
    farm_location   TEXT DEFAULT '',
    farm_size_acres REAL DEFAULT 0.0,
    created_at      TEXT NOT NULL,
    last_login_at   TEXT,
    is_active       INTEGER DEFAULT 1
);

-- ── Auth tokens (session persistence across restarts) ─────────────────────
CREATE TABLE IF NOT EXISTS auth_tokens (
    token       TEXT PRIMARY KEY,
    username    TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (username) REFERENCES farmers(username) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tokens_username ON auth_tokens(username);
CREATE INDEX IF NOT EXISTS idx_tokens_expires  ON auth_tokens(expires_at);

-- ── ESP32 sensor readings history ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sensor_readings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    temperature     REAL,
    humidity        REAL,
    soil_moisture   INTEGER,
    soil_raw        INTEGER,
    pir_motion      INTEGER DEFAULT 0,
    flame_detected  INTEGER DEFAULT 0,
    light_intensity INTEGER DEFAULT 0,
    co2_ppm         INTEGER DEFAULT 400,
    source          TEXT DEFAULT 'esp32',
    recorded_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sensor_time ON sensor_readings(recorded_at);

-- ── Crop recommendation history (per farmer) ──────────────────────────────
CREATE TABLE IF NOT EXISTS recommendations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL,
    n_value         REAL,
    p_value         REAL,
    k_value         REAL,
    ph_value        REAL,
    temperature     REAL,
    humidity        REAL,
    rainfall        REAL,
    top_crop        TEXT,
    all_results     TEXT,      -- JSON blob of full recommendation array
    fertilizer_tips TEXT,      -- JSON blob
    parse_method    TEXT,      -- how document was parsed (if uploaded)
    created_at      TEXT NOT NULL,
    FOREIGN KEY (username) REFERENCES farmers(username) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_rec_username ON recommendations(username);
CREATE INDEX IF NOT EXISTS idx_rec_time     ON recommendations(created_at);

-- ── Disease detection log (per farmer) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS disease_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL,
    disease_label   TEXT NOT NULL,
    disease_display TEXT NOT NULL,
    confidence      REAL,
    severity        TEXT,
    is_healthy      INTEGER DEFAULT 0,
    treatments      TEXT,      -- JSON array
    image_filename  TEXT,
    demo_mode       INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (username) REFERENCES farmers(username) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_disease_username ON disease_logs(username);
CREATE INDEX IF NOT EXISTS idx_disease_time     ON disease_logs(created_at);

-- ── Field alerts log ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type  TEXT NOT NULL,
    severity    TEXT NOT NULL,
    message     TEXT NOT NULL,
    sensor_data TEXT,          -- JSON snapshot of readings at time of alert
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alert_time ON alert_logs(created_at);
"""


# ════════════════════════════════════════════════════════════════════════════
#  DATABASE CLASS
# ════════════════════════════════════════════════════════════════════════════

class SmartAgroDB:
    """All database operations for SmartAgro."""

    def init(self):
        """Create tables if they don't exist. Call once at app startup."""
        with _conn() as con:
            con.executescript(_SCHEMA)
        logger.info(f"SmartAgro DB ready — {DB_PATH}")

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()

    @staticmethod
    def _row_to_dict(row) -> dict:
        return dict(row) if row else None

    # ════════════════════════════════════════════════════════════════════════
    #  FARMER ACCOUNTS
    # ════════════════════════════════════════════════════════════════════════

    def save_farmer(self, username: str, password_hash: str, email: str,
                    full_name: str, phone: str = "", farm_location: str = "",
                    farm_size_acres: float = 0.0) -> bool:
        """
        Insert a new farmer. Returns True on success, False if username/email taken.
        """
        try:
            with _write_lock, _conn() as con:
                con.execute("""
                    INSERT INTO farmers
                        (username, password_hash, email, full_name, phone,
                         farm_location, farm_size_acres, created_at)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (username, password_hash, email, full_name, phone,
                      farm_location, farm_size_acres, self._now()))
            logger.info(f"Farmer registered: {username}")
            return True
        except sqlite3.IntegrityError as e:
            logger.warning(f"Farmer save conflict: {e}")
            return False

    def get_farmer(self, username: str) -> dict | None:
        """Fetch farmer record by username."""
        with _conn() as con:
            row = con.execute(
                "SELECT * FROM farmers WHERE username=? AND is_active=1", (username,)
            ).fetchone()
        return self._row_to_dict(row)

    def get_farmer_by_email(self, email: str) -> dict | None:
        with _conn() as con:
            row = con.execute(
                "SELECT * FROM farmers WHERE email=? AND is_active=1", (email,)
            ).fetchone()
        return self._row_to_dict(row)

    def update_last_login(self, username: str):
        with _write_lock, _conn() as con:
            con.execute(
                "UPDATE farmers SET last_login_at=? WHERE username=?",
                (self._now(), username)
            )

    def update_farmer_profile(self, username: str, **fields) -> bool:
        """
        Update farmer profile fields. Allowed: full_name, phone, farm_location, farm_size_acres.
        Example: db.update_farmer_profile("ravi", phone="9876543210", farm_location="Coimbatore")
        """
        allowed = {"full_name", "phone", "farm_location", "farm_size_acres"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        cols = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [username]
        with _write_lock, _conn() as con:
            con.execute(f"UPDATE farmers SET {cols} WHERE username=?", vals)
        return True

    def get_all_farmers(self) -> list:
        """Admin: list all active farmers (no password hashes)."""
        with _conn() as con:
            rows = con.execute("""
                SELECT username, email, full_name, phone, farm_location,
                       farm_size_acres, created_at, last_login_at
                FROM farmers WHERE is_active=1
                ORDER BY created_at DESC
            """).fetchall()
        return [dict(r) for r in rows]

    def delete_farmer(self, username: str):
        """Soft delete — marks is_active=0, cascades tokens."""
        with _write_lock, _conn() as con:
            con.execute("UPDATE farmers SET is_active=0 WHERE username=?", (username,))

    # ════════════════════════════════════════════════════════════════════════
    #  AUTH TOKENS
    # ════════════════════════════════════════════════════════════════════════

    def save_token(self, token: str, username: str, expires_at: str):
        """Persist a login token so it survives server restarts."""
        with _write_lock, _conn() as con:
            con.execute("""
                INSERT OR REPLACE INTO auth_tokens (token, username, expires_at, created_at)
                VALUES (?,?,?,?)
            """, (token, username, expires_at, self._now()))

    def get_token(self, token: str) -> str | None:
        """
        Verify token exists and is not expired.
        Returns username if valid, None if invalid/expired.
        """
        with _conn() as con:
            row = con.execute(
                "SELECT username, expires_at FROM auth_tokens WHERE token=?", (token,)
            ).fetchone()
        if not row:
            return None
        if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
            self.delete_token(token)   # clean up expired token
            return None
        return row["username"]

    def delete_token(self, token: str):
        """Remove a single token (logout)."""
        with _write_lock, _conn() as con:
            con.execute("DELETE FROM auth_tokens WHERE token=?", (token,))

    def purge_expired_tokens(self):
        """Remove all expired tokens. Call periodically or at startup."""
        with _write_lock, _conn() as con:
            cur = con.execute(
                "DELETE FROM auth_tokens WHERE expires_at < ?", (self._now(),)
            )
            count = cur.rowcount
        if count:
            logger.info(f"Purged {count} expired auth tokens")

    def get_active_token_count(self) -> int:
        with _conn() as con:
            return con.execute(
                "SELECT COUNT(*) FROM auth_tokens WHERE expires_at > ?", (self._now(),)
            ).fetchone()[0]

    # ════════════════════════════════════════════════════════════════════════
    #  SENSOR READINGS
    # ════════════════════════════════════════════════════════════════════════

    def save_sensor(self, data: dict):
        """
        Persist one ESP32 sensor reading.
        Auto-prunes table to last 1000 rows to avoid unbounded growth.
        """
        with _write_lock, _conn() as con:
            con.execute("""
                INSERT INTO sensor_readings
                    (temperature, humidity, soil_moisture, soil_raw,
                     pir_motion, flame_detected, light_intensity, co2_ppm,
                     source, recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                data.get("temperature"),
                data.get("humidity"),
                data.get("soil_moisture"),
                data.get("soil_raw", 0),
                int(data.get("pir_motion", False)),
                int(data.get("flame_detected", False)),
                data.get("light_intensity", 0),
                data.get("co2_ppm", 400),
                data.get("source", "esp32"),
                self._now(),
            ))
            # Keep only latest 1000 rows
            con.execute("""
                DELETE FROM sensor_readings
                WHERE id NOT IN (
                    SELECT id FROM sensor_readings ORDER BY id DESC LIMIT 1000
                )
            """)

    def get_sensor_history(self, n: int = 50) -> list:
        """Return last N sensor readings, newest first."""
        n = min(n, 500)
        with _conn() as con:
            rows = con.execute("""
                SELECT * FROM sensor_readings
                ORDER BY id DESC LIMIT ?
            """, (n,)).fetchall()
        return [dict(r) for r in rows]

    def get_latest_sensor(self) -> dict | None:
        """Return the single most recent sensor reading."""
        with _conn() as con:
            row = con.execute(
                "SELECT * FROM sensor_readings ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return self._row_to_dict(row)

    # ════════════════════════════════════════════════════════════════════════
    #  CROP RECOMMENDATIONS
    # ════════════════════════════════════════════════════════════════════════

    def save_recommendation(self, username: str, params: dict,
                             results: list, fertilizer_tips: list,
                             parse_method: str = None) -> int:
        """
        Save a completed crop recommendation.
        Returns the new row ID.
        """
        top_crop = results[0]["crop"] if results else "unknown"
        with _write_lock, _conn() as con:
            cur = con.execute("""
                INSERT INTO recommendations
                    (username, n_value, p_value, k_value, ph_value,
                     temperature, humidity, rainfall,
                     top_crop, all_results, fertilizer_tips, parse_method, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                username,
                params.get("N"),
                params.get("P"),
                params.get("K"),
                params.get("ph"),
                params.get("temperature"),
                params.get("humidity"),
                params.get("rainfall"),
                top_crop,
                json.dumps(results),
                json.dumps(fertilizer_tips),
                parse_method,
                self._now(),
            ))
            return cur.lastrowid

    def get_recommendations(self, username: str, limit: int = 20) -> list:
        """Return a farmer's recommendation history, newest first."""
        with _conn() as con:
            rows = con.execute("""
                SELECT id, top_crop, n_value, p_value, k_value, ph_value,
                       temperature, humidity, rainfall,
                       all_results, fertilizer_tips, parse_method, created_at
                FROM recommendations
                WHERE username=?
                ORDER BY id DESC LIMIT ?
            """, (username, limit)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["all_results"]     = json.loads(d["all_results"]     or "[]")
            d["fertilizer_tips"] = json.loads(d["fertilizer_tips"] or "[]")
            out.append(d)
        return out

    def get_all_recommendations(self, limit: int = 100) -> list:
        """Admin: all recommendations across all farmers."""
        with _conn() as con:
            rows = con.execute("""
                SELECT r.*, f.full_name
                FROM recommendations r
                JOIN farmers f ON r.username = f.username
                ORDER BY r.id DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ════════════════════════════════════════════════════════════════════════
    #  DISEASE DETECTION LOGS
    # ════════════════════════════════════════════════════════════════════════

    def save_disease_log(self, username: str, disease_label: str,
                          disease_display: str, confidence: float,
                          severity: str, is_healthy: bool,
                          treatments: list, image_filename: str = "",
                          demo_mode: bool = False) -> int:
        """Save a disease detection result. Returns new row ID."""
        with _write_lock, _conn() as con:
            cur = con.execute("""
                INSERT INTO disease_logs
                    (username, disease_label, disease_display, confidence,
                     severity, is_healthy, treatments, image_filename,
                     demo_mode, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                username,
                disease_label,
                disease_display,
                confidence,
                severity,
                int(is_healthy),
                json.dumps(treatments),
                image_filename,
                int(demo_mode),
                self._now(),
            ))
            return cur.lastrowid

    def get_disease_logs(self, username: str, limit: int = 20) -> list:
        """Return a farmer's disease detection history, newest first."""
        with _conn() as con:
            rows = con.execute("""
                SELECT id, disease_display, confidence, severity,
                       is_healthy, treatments, image_filename, demo_mode, created_at
                FROM disease_logs
                WHERE username=?
                ORDER BY id DESC LIMIT ?
            """, (username, limit)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["treatments"] = json.loads(d["treatments"] or "[]")
            d["is_healthy"] = bool(d["is_healthy"])
            d["demo_mode"]  = bool(d["demo_mode"])
            out.append(d)
        return out

    # ════════════════════════════════════════════════════════════════════════
    #  ALERT LOGS
    # ════════════════════════════════════════════════════════════════════════

    def save_alert(self, alert_type: str, severity: str,
                   message: str, sensor_snapshot: dict = None):
        """Log a field alert (flame, low moisture, high temp, etc.)."""
        with _write_lock, _conn() as con:
            con.execute("""
                INSERT INTO alert_logs (alert_type, severity, message, sensor_data, created_at)
                VALUES (?,?,?,?,?)
            """, (
                alert_type,
                severity,
                message,
                json.dumps(sensor_snapshot) if sensor_snapshot else None,
                self._now(),
            ))

    def get_alert_logs(self, limit: int = 50) -> list:
        with _conn() as con:
            rows = con.execute("""
                SELECT * FROM alert_logs ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("sensor_data"):
                d["sensor_data"] = json.loads(d["sensor_data"])
            out.append(d)
        return out

    # ════════════════════════════════════════════════════════════════════════
    #  FARMER STATISTICS (for dashboard)
    # ════════════════════════════════════════════════════════════════════════

    def get_farmer_stats(self, username: str) -> dict:
        """
        Aggregated stats for one farmer's dashboard:
          - total recommendations run
          - most recommended crop
          - total disease scans
          - most common disease found
          - days since registration
        """
        with _conn() as con:
            rec_count = con.execute(
                "SELECT COUNT(*) FROM recommendations WHERE username=?", (username,)
            ).fetchone()[0]

            top_crop_row = con.execute("""
                SELECT top_crop, COUNT(*) as cnt
                FROM recommendations WHERE username=?
                GROUP BY top_crop ORDER BY cnt DESC LIMIT 1
            """, (username,)).fetchone()

            disease_count = con.execute(
                "SELECT COUNT(*) FROM disease_logs WHERE username=? AND is_healthy=0",
                (username,)
            ).fetchone()[0]

            healthy_count = con.execute(
                "SELECT COUNT(*) FROM disease_logs WHERE username=? AND is_healthy=1",
                (username,)
            ).fetchone()[0]

            top_disease_row = con.execute("""
                SELECT disease_display, COUNT(*) as cnt
                FROM disease_logs WHERE username=? AND is_healthy=0
                GROUP BY disease_display ORDER BY cnt DESC LIMIT 1
            """, (username,)).fetchone()

            farmer = con.execute(
                "SELECT created_at FROM farmers WHERE username=?", (username,)
            ).fetchone()

        days_active = 0
        if farmer and farmer["created_at"]:
            try:
                created = datetime.fromisoformat(farmer["created_at"])
                days_active = (datetime.utcnow() - created).days
            except Exception:
                pass

        return {
            "total_recommendations":  rec_count,
            "most_recommended_crop":  top_crop_row["top_crop"] if top_crop_row else None,
            "total_disease_scans":    disease_count + healthy_count,
            "disease_detections":     disease_count,
            "healthy_detections":     healthy_count,
            "most_common_disease":    top_disease_row["disease_display"] if top_disease_row else None,
            "days_active":            days_active,
        }

    def get_global_stats(self) -> dict:
        """Platform-wide stats for admin or status endpoint."""
        with _conn() as con:
            farmers    = con.execute("SELECT COUNT(*) FROM farmers WHERE is_active=1").fetchone()[0]
            tokens     = self.get_active_token_count()
            sensor_cnt = con.execute("SELECT COUNT(*) FROM sensor_readings").fetchone()[0]
            rec_cnt    = con.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
            disease_cnt= con.execute("SELECT COUNT(*) FROM disease_logs").fetchone()[0]
        return {
            "registered_farmers":   farmers,
            "active_sessions":      tokens,
            "sensor_readings_stored": sensor_cnt,
            "recommendations_run":  rec_cnt,
            "disease_scans_run":    disease_cnt,
        }


# ── Singleton instance ────────────────────────────────────────────────────────
db = SmartAgroDB()

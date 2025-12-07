from flask import Flask, jsonify, request
from datetime import datetime
from typing import List, Dict, Any, Optional
import json
import os

from modules.radar_engine import run_radar_engine

app = Flask(__name__)

# --------------------------------------------------
# LOG HELPERS
# --------------------------------------------------

LOG_DIR = "logs"


def ensure_log_dir() -> None:
    """Ensure logs directory exists."""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)


def log_write(module_name: str, entry: dict) -> None:
    """
    T4 backend modül log giriş noktası.
    Her modül çalıştığında o güne ait log dosyasına ek yapar.
    """
    ensure_log_dir()

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_path = os.path.join(LOG_DIR, f"{date_str}_pipeline.json")

    # Var olan logu oku
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"date": date_str, "modules": []}
    else:
        data = {"date": date_str, "modules": []}

    # Yeni kayıt ekle
    data["modules"].append({
        "module": module_name,
        "ts": datetime.utcnow().isoformat() + "Z",
        **entry
    })

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.utcnow().isoformat() + "Z"


def load_symbols() -> List[str]:
    """Load symbols from symbols_list.json"""
    try:
        path = "symbols_list.json"
        if not os.path.exists(path):
            print("symbols_list.json not found.")
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                return []
    except Exception as e:
        print("load_symbols ERROR:", e)
        return []


# --------------------------------------------------
# (GLOBAL STATE KALDIRILDI)
# --------------------------------------------------


# --------------------------------------------------
# ENDPOINTS
# --------------------------------------------------

@app.route("/", methods=["GET"])
def root():
    return "T4 backend running", 200


@app.route("/status", methods=["GET"])
def status():
    # pipeline_state kaldırıldığı için sabit bir dummy response döndürüyoruz
    return jsonify({
        "pipeline_status": "DISABLED",
        "message": "Morning pipeline is removed."
    }), 200


@app.route("/result", methods=["GET"])
def result():
    # result_state kaldırıldığı için sabit bir dummy response döndürüyoruz
    return jsonify({
        "result_ready": False,
        "message": "No pipeline results. Morning pipeline is removed."
    }), 200


@app.route("/logs/today", methods=["GET"])
def logs_today():
    """
    Bugüne ait pipeline log dosyasını JSON olarak döner.
    Dosya yoksa basit bir mesaj döner.
    """
    ensure_log_dir()

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_path = os.path.join(LOG_DIR, f"{date_str}_pipeline.json")

    if not os.path.exists(log_path):
        return jsonify({
            "date": date_str,
            "message": "No log file for today."
        }), 200

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({
            "date": date_str,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)


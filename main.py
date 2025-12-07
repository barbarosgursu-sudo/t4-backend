from flask import Flask, request, jsonify
from typing import Dict, Any, List
import json
import os
from datetime import datetime

# Radar engine (kullanılmaya devam ediyor)
from modules.radar_engine import run_radar_engine

# Yeni yazılacak modüller (şimdilik boş placeholder)
# from modules.core10_engine import run_core10_engine
# from modules.trade_log_engine import run_trade_log_engine

app = Flask(__name__)

LOG_DIR = "logs"

def ensure_log_dir():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

def log_write(module_name: str, entry: dict):
    ensure_log_dir()
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_path = os.path.join(LOG_DIR, f"{date_str}.json")

    try:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"date": date_str, "logs": []}
    except:
        data = {"date": date_str, "logs": []}

    data["logs"].append({
        "module": module_name,
        "ts": datetime.utcnow().isoformat() + "Z",
        **entry
    })

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ----------------------------------------------------
#  YENİ TEK ENDPOINT
#  /runRadarPipeline
#  GAS radar_candidates_api tablosunu JSON olarak gönderir
#  Railway → radar_picks / core10 / trade_log hesaplar
# ----------------------------------------------------
@app.route("/runRadarPipeline", methods=["POST"])
def run_radar_pipeline():

    body: Dict[str, Any] = request.get_json(silent=True) or {}

    # Beklenen giriş:
    # {
    #   "radar_candidates": [...],     # GAS tablosundan JSON
    #   "regime": { "regime": "YELLOW" }
    # }

    radar_candidates: List[Dict[str, Any]] = body.get("radar_candidates", []) or []
    regime_info: Dict[str, Any] = body.get("regime", {"regime": "YELLOW"})

    try:
        # --- 1) RADAR PICKS ---
        radar_context = {
            "radar_candidates": radar_candidates,
            "regime": regime_info,
            "config": {
                "macro_mult_GREEN": 1.05,
                "macro_mult_YELLOW": 1.00,
                "macro_mult_RED": 0.90,
                "RADAR_LIQ_MIN": 1_000_000,
                "RADAR_USE_SECTOR_CAP": False,
                "RADAR_SECTOR_CAP": 2,
            }
        }

        radar_out = run_radar_engine(radar_context)
        radar_picks = radar_out.get("radar", [])
        radar_debug = radar_out.get("radar_debug", [])
        radar_summary = radar_out.get("radar_summary", {})
        radar_api = radar_out.get("radar_api", [])

        # --- 2) CORE10 (henüz dummy, sonra gerçek modül yazılacak) ---
        core10_list = radar_picks[:10]

        # --- 3) TRADE LOG (henüz dummy placeholder) ---
        trade_log = []   # Sonradan gerçek delta analizi eklenecek

        # LOG
        log_write("run_radar_pipeline", {
            "status": "OK",
            "radar_candidates": len(radar_candidates),
            "radar_picks": len(radar_picks),
            "core10": len(core10_list),
        })

        # GERİ DÖNÜŞ
        return jsonify({
            "status": "ok",
            "radar_picks": radar_picks,
            "radar_debug": radar_debug,
            "radar_summary": radar_summary,
            "radar_api": radar_api,
            "core10": core10_list,
            "trade_log": trade_log,
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/", methods=["GET"])
def root():
    return "T4 Radar Backend Active", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

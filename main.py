import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def root():
    return jsonify({"status": "ok", "message": "t4-backend-root"}), 200

@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok", "message": "pong"}), 200

@app.route("/runMorningPipeline", methods=["POST"])
def run_morning_pipeline():
    """
    Þimdilik DUMMY.
    Gerçekte burada:
      - snapshot
      - fetch
      - repair
      - indicators
      - radar
      - regime
      - core10
      - tuning
    çalýþacak ve status/result JSON üretecek.
    Þu an sadece sabit sahte veri döndürüyoruz.
    """
    status = {
        "pipeline_status": "DONE_DUMMY",
        "modules": [
            {"name": "snapshot", "status": "OK"},
            {"name": "fetch", "status": "OK"},
            {"name": "repair", "status": "OK"},
            {"name": "indicators", "status": "OK"},
            {"name": "radar", "status": "OK"},
            {"name": "regime", "status": "OK"},
            {"name": "core10", "status": "OK"},
            {"name": "tuning", "status": "OK"},
        ]
    }

    result = {
        "snapshot_data": None,
        "fetch_data": None,
        "indicators": None,
        "radar_output": None,
        "regime_output": None,
        "core10_output": None,
        "tuning_output": None,
    }

    return jsonify({
        "status_json": status,
        "result_json": result
    }), 200


if __name__ == "__main__":
    # Railway, PORT environment variable'ýný set ediyor.
    # Lokalde çalýþtýrýrken varsayýlan 8000.
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

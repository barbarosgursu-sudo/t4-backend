from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/", methods=["GET"])
def root():
    return "T4 backend running", 200


@app.route("/runMorningPipeline", methods=["POST"])
def run_morning_pipeline():
    # Şimdilik sadece dummy cevap
    return jsonify({
        "status": "ok",
        "pipeline": "not_implemented_yet"
    }), 200


@app.route("/status", methods=["GET"])
def status():
    # Şimdilik tamamen dummy
    return jsonify({
        "pipeline_status": "IDLE",
        "last_run": None,
        "modules": []
    }), 200


@app.route("/result", methods=["GET"])
def result():
    # Şimdilik tamamen dummy
    return jsonify({
        "result_ready": False,
        "radar": [],
        "core10": []
    }), 200


if __name__ == "__main__":
    # Lokalde test için; Railway gunicorn kullanacak
    app.run(host="0.0.0.0", port=8080)

import os
from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def hello():
    """Root endpoint returning a hello world message."""
    return jsonify(
        message="Hello World from Cloud Run with Aqua MicroEnforcer!",
        service="microenforcer-flask",
        status="running",
    )


@app.route("/healthz")
def health():
    """Health check endpoint for Cloud Run."""
    return jsonify(status="healthy"), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

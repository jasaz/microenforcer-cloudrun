import os
import subprocess
import tempfile
from flask import Flask, jsonify

app = Flask(__name__)

# EICAR anti-malware test string (not actual malware)
# See: https://www.eicar.org/download-anti-malware-testfile/
EICAR_TEST_STRING = (
    r"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)


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


@app.route("/test-malware")
def test_malware():
    """
    Creates and attempts to execute the EICAR anti-malware test file.
    Tests whether MicroEnforcer detects/blocks malware at runtime.
    The EICAR file is a harmless test string recognized by all AV engines.
    """
    results = {
        "test": "EICAR Anti-Malware Test",
        "steps": [],
    }

    eicar_path = os.path.join(tempfile.gettempdir(), "eicar_test.com")

    # Step 1: Write EICAR test file to disk
    try:
        with open(eicar_path, "w") as f:
            f.write(EICAR_TEST_STRING)
        results["steps"].append({
            "step": "write_file",
            "status": "success",
            "detail": f"EICAR test file written to {eicar_path}",
        })
    except Exception as e:
        results["steps"].append({
            "step": "write_file",
            "status": "blocked",
            "detail": str(e),
        })
        results["conclusion"] = "MicroEnforcer BLOCKED file creation"
        return jsonify(results), 200

    # Step 2: Make it executable
    try:
        os.chmod(eicar_path, 0o755)
        results["steps"].append({
            "step": "chmod_executable",
            "status": "success",
            "detail": f"Set executable permission on {eicar_path}",
        })
    except Exception as e:
        results["steps"].append({
            "step": "chmod_executable",
            "status": "blocked",
            "detail": str(e),
        })

    # Step 3: Attempt to execute the EICAR file
    try:
        result = subprocess.run(
            [eicar_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        results["steps"].append({
            "step": "execute_file",
            "status": "executed",
            "detail": f"Exit code: {result.returncode}, stderr: {result.stderr[:500] if result.stderr else 'none'}",
        })
        results["conclusion"] = "MicroEnforcer did NOT block execution (audit-only mode likely)"
    except PermissionError as e:
        results["steps"].append({
            "step": "execute_file",
            "status": "blocked",
            "detail": str(e),
        })
        results["conclusion"] = "MicroEnforcer BLOCKED execution"
    except subprocess.TimeoutExpired:
        results["steps"].append({
            "step": "execute_file",
            "status": "timeout",
            "detail": "Execution timed out after 5 seconds",
        })
        results["conclusion"] = "Execution timed out"
    except Exception as e:
        results["steps"].append({
            "step": "execute_file",
            "status": "error",
            "detail": str(e),
        })
        results["conclusion"] = f"Execution failed: {type(e).__name__}"

    # Step 4: Cleanup
    try:
        os.remove(eicar_path)
        results["steps"].append({
            "step": "cleanup",
            "status": "success",
            "detail": "EICAR test file removed",
        })
    except Exception:
        pass

    return jsonify(results), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

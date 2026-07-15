import os
import socket
import subprocess
import tempfile
import time
from flask import Flask, jsonify, request

app = Flask(__name__)

# Test file used for file block operations
TEST_FILE_DIR = tempfile.gettempdir()
TEST_FILE_PATH = os.path.join(TEST_FILE_DIR, "protected_test_file.txt")


@app.route("/")
def hello():
    """Root endpoint returning a hello world message."""

    # Add a 30 sec delay
    time.sleep(30)
    return jsonify(
        message="Hello World from Cloud Run with Aqua MicroEnforcer!",
        service="microenforcer-flask",
        status="running",
    )


@app.route("/healthz")
def health():
    """Health check endpoint for Cloud Run."""
    return jsonify(status="healthy"), 200


@app.route("/test-file-block")
def test_file_block():
    """
    Tests MicroEnforcer file block policy by attempting read, modify, and
    execute operations on a file.

    Query params:
      - path: (optional) custom file path to test against (default: /tmp/protected_test_file.txt)

    Usage:
      GET /test-file-block
      GET /test-file-block?path=/etc/passwd
    """
    target_path = request.args.get("path", TEST_FILE_PATH)

    results = {
        "test": "File Block Test",
        "target_file": target_path,
        "operations": [],
    }

    # --- Setup: create the test file if it doesn't exist ---
    if not os.path.exists(target_path):
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w") as f:
                f.write("This is a test file for MicroEnforcer file block policy.\n")
            os.chmod(target_path, 0o755)
            results["setup"] = f"Test file created at {target_path}"
        except Exception as e:
            results["setup"] = f"Could not create test file: {e}"

    # --- Test 1: READ ---
    try:
        with open(target_path, "r") as f:
            content = f.read(256)
        results["operations"].append({
            "operation": "read",
            "status": "allowed",
            "detail": f"Read {len(content)} bytes from {target_path}",
        })
    except PermissionError as e:
        results["operations"].append({
            "operation": "read",
            "status": "BLOCKED",
            "detail": str(e),
        })
    except Exception as e:
        results["operations"].append({
            "operation": "read",
            "status": "error",
            "detail": f"{type(e).__name__}: {e}",
        })

    # --- Test 2: MODIFY (append) ---
    try:
        with open(target_path, "a") as f:
            f.write("Modified by file block test.\n")
        results["operations"].append({
            "operation": "modify",
            "status": "allowed",
            "detail": f"Appended data to {target_path}",
        })
    except PermissionError as e:
        results["operations"].append({
            "operation": "modify",
            "status": "BLOCKED",
            "detail": str(e),
        })
    except Exception as e:
        results["operations"].append({
            "operation": "modify",
            "status": "error",
            "detail": f"{type(e).__name__}: {e}",
        })

    # --- Test 3: EXECUTE ---
    try:
        result = subprocess.run(
            [target_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        results["operations"].append({
            "operation": "execute",
            "status": "allowed",
            "detail": f"Exit code: {result.returncode}, stderr: {result.stderr[:200] if result.stderr else 'none'}",
        })
    except PermissionError as e:
        results["operations"].append({
            "operation": "execute",
            "status": "BLOCKED",
            "detail": str(e),
        })
    except subprocess.TimeoutExpired:
        results["operations"].append({
            "operation": "execute",
            "status": "timeout",
            "detail": "Execution timed out after 5 seconds",
        })
    except OSError as e:
        results["operations"].append({
            "operation": "execute",
            "status": "BLOCKED" if e.errno == 13 else "error",
            "detail": f"{type(e).__name__}: {e}",
        })
    except Exception as e:
        results["operations"].append({
            "operation": "execute",
            "status": "error",
            "detail": f"{type(e).__name__}: {e}",
        })

    # --- Summary ---
    blocked_count = sum(
        1 for op in results["operations"] if op["status"] == "BLOCKED"
    )
    results["summary"] = {
        "total_operations": len(results["operations"]),
        "blocked": blocked_count,
        "allowed": len(results["operations"]) - blocked_count,
        "conclusion": (
            "MicroEnforcer BLOCKED all file operations"
            if blocked_count == len(results["operations"])
            else f"MicroEnforcer blocked {blocked_count}/{len(results['operations'])} operations"
        ),
    }

    return jsonify(results), 200


@app.route("/test-port-block")
def test_port_block():
    """
    Tests MicroEnforcer port block policy by attempting outbound TCP
    connections to external hosts on specified ports, and inbound
    listening on those ports.

    Query params:
      - ports: (optional) comma-separated list of ports to test
               (default: 22,23,25,3306,5432,6379)
      - host:  (optional) target host for outbound test
               (default: 8.8.8.8 — Google DNS, external)

    Usage:
      GET /test-port-block
      GET /test-port-block?ports=3306
      GET /test-port-block?ports=22,3306,5432&host=203.0.113.1
    """
    default_ports = "22,23,25,3306,5432,6379"
    ports_str = request.args.get("ports", default_ports)
    target_host = request.args.get("host", "8.8.8.8")

    try:
        ports = [int(p.strip()) for p in ports_str.split(",")]
    except ValueError:
        return jsonify(error="Invalid port format. Use comma-separated integers."), 400

    results = {
        "test": "Port Block Test",
        "target_host": target_host,
        "ports_tested": ports,
        "results": [],
    }

    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        try:
            sock.connect((target_host, port))
            results["results"].append({
                "port": port,
                "status": "allowed",
                "detail": f"TCP connection to {target_host}:{port} succeeded",
            })
        except ConnectionRefusedError:
            results["results"].append({
                "port": port,
                "status": "refused",
                "detail": f"Connection refused (port not listening, but NOT blocked by policy)",
            })
        except PermissionError as e:
            results["results"].append({
                "port": port,
                "status": "BLOCKED",
                "detail": f"MicroEnforcer blocked connection: {e}",
            })
        except socket.timeout:
            results["results"].append({
                "port": port,
                "status": "timeout",
                "detail": f"Connection timed out (could be blocked or unreachable)",
            })
        except OSError as e:
            results["results"].append({
                "port": port,
                "status": "BLOCKED" if e.errno == 13 else "error",
                "detail": f"{type(e).__name__}: {e}",
            })
        except Exception as e:
            results["results"].append({
                "port": port,
                "status": "error",
                "detail": f"{type(e).__name__}: {e}",
            })
        finally:
            sock.close()

    # --- Also test binding/listening on ports ---
    results["listen_tests"] = []
    for port in ports:
        listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_sock.settimeout(1)
        try:
            listen_sock.bind(("0.0.0.0", port))
            listen_sock.listen(1)
            results["listen_tests"].append({
                "port": port,
                "status": "allowed",
                "detail": f"Successfully bound and listening on port {port}",
            })
        except PermissionError as e:
            results["listen_tests"].append({
                "port": port,
                "status": "BLOCKED",
                "detail": f"MicroEnforcer blocked listen: {e}",
            })
        except OSError as e:
            status = "BLOCKED" if e.errno == 13 else "in_use" if e.errno == 98 else "error"
            results["listen_tests"].append({
                "port": port,
                "status": status,
                "detail": f"{type(e).__name__}: {e}",
            })
        except Exception as e:
            results["listen_tests"].append({
                "port": port,
                "status": "error",
                "detail": f"{type(e).__name__}: {e}",
            })
        finally:
            listen_sock.close()

    # --- Summary ---
    connect_blocked = sum(
        1 for r in results["results"] if r["status"] == "BLOCKED"
    )
    listen_blocked = sum(
        1 for r in results["listen_tests"] if r["status"] == "BLOCKED"
    )
    results["summary"] = {
        "outbound_blocked": f"{connect_blocked}/{len(ports)}",
        "inbound_blocked": f"{listen_blocked}/{len(ports)}",
        "conclusion": (
            f"MicroEnforcer blocked {connect_blocked} outbound and {listen_blocked} inbound port connections"
        ),
    }

    return jsonify(results), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

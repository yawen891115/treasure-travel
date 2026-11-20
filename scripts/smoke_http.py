"""Exercise real localhost HTTP, CSRF/session, chat, feedback and reset with no paid APIs."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import config  # noqa: E402


def main():
    audit = ROOT / "audit"
    audit.mkdir(exist_ok=True)
    env = {
        **os.environ,
        "AGENT_BACKEND": "offline",
        "MAPS_MODE": "offline",
        "DB_DIR": str(audit / "http_test_db"),
    }
    subprocess.run(
        [sys.executable, str(ROOT / "web/manage.py"), "migrate", "--noinput"],
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    with (audit / "http_server.log").open("w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "web/manage.py"),
                "runserver",
                f"127.0.0.1:{port}",
                "--noreload",
            ],
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            session = requests.Session()
            session.trust_env = False
            for _ in range(100):
                try:
                    home = session.get(url + "/", timeout=2)
                    break
                except requests.ConnectionError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("server failed to start")
            headers = {"X-CSRFToken": session.cookies.get("csrftoken"), "Referer": url + "/"}
            origin = "41.83, -71.41" if config.dataset_state() == "FAKE" else "42.3601, -71.0589"
            prompt = (
                "Saturday 10:00-18:00, 2 people, budget $100, walk, max 20 minutes, "
                f"origin ({origin}), interests: art and coffee"
            )
            chat = session.post(url + "/api/chat", json={"message": prompt}, headers=headers)
            assert home.status_code == chat.status_code == 200
            stops = chat.json()["stops"]
            assert stops, "expected a nonempty local demonstration"
            feedback = session.post(
                url + "/api/feedback",
                json={"place_id": stops[0]["place_id"], "liked": True},
                headers=headers,
            )
            reset = session.post(url + "/api/reset", json={}, headers=headers)
            assert feedback.status_code == reset.status_code == 200
            result = {
                "home_status": home.status_code,
                "chat_status": chat.status_code,
                "feedback_status": feedback.status_code,
                "reset_status": reset.status_code,
                "backend": "offline rules; no real LLM/Maps API",
                "response": chat.json(),
            }
            (audit / "http_demo.json").write_text(json.dumps(result, indent=2))
            print(json.dumps(result, indent=2))
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()

import os
import subprocess
import sys


def run(command: list[str]) -> None:
    print(f"Running: {' '.join(command)}", flush=True)
    subprocess.run(command, check=True)


def main() -> None:
    run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"])
    if os.getenv("DEMO_SEED_ENABLED", "false").lower() == "true":
        run([sys.executable, "seed_demo.py"])

    port = os.getenv("PORT", "8000")
    os.execvp(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
        ],
    )


if __name__ == "__main__":
    main()

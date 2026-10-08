"""
auto_scraper_detalle.py
Ejecuta scrapper_detalle.py repetidamente hasta que aparezca el flag
'listing_finished.flag' (que el scraper escribe al agotar el listado).
"""
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
SCRAPPER = SCRIPT_DIR / "scrapper_detalle.py"
INTERVAL_MINUTES = 0.5                     # pausa entre corridas
SUBPROCESS_TIMEOUT = 1800                 # 30 min máximo por corrida

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = REPO_ROOT / "data" / "bronze"
FINISHED_FLAG = OUTPUT_DIR / "listing_finished.flag"
PROGRESS_FILE = OUTPUT_DIR / "progress_detalle.json"
PAGES_FILE = OUTPUT_DIR / "progress_pages.json"
LOG_FILE = OUTPUT_DIR / "auto_scraper_detalle.log"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Keep legacy Windows consoles from failing when log messages contain Unicode.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")


def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def status_summary() -> str:
    """Resumen rápido de progreso para el log."""
    parts = []
    if PAGES_FILE.exists():
        try:
            import json
            with open(PAGES_FILE) as f:
                data = json.load(f)
            parts.append(f"páginas done: {len(data.get('done_pages', []))}")
        except Exception:
            pass
    if PROGRESS_FILE.exists():
        try:
            import json
            with open(PROGRESS_FILE) as f:
                data = json.load(f)
            parts.append(
                f"URLs done: {len(data.get('done_urls', []))} | "
                f"skipped: {len(data.get('skipped_urls', []))} | "
                f"failed: {len(data.get('failed_urls', []))}"
            )
        except Exception:
            pass
    return " | ".join(parts) if parts else "(sin datos)"


# ============================================================
# MAIN LOOP
# ============================================================
log("=" * 60)
log("Auto-scraper-detalle iniciado")
log(f"Scrapper: {SCRAPPER}")
log(f"Intervalo: {INTERVAL_MINUTES} min entre corridas")
log("=" * 60)

run_number = 0
while True:
    if FINISHED_FLAG.exists():
        log("Flag 'listing_finished.flag' detectado. Terminando.")
        break

    run_number += 1
    log(f"--- Corrida #{run_number} ---")
    log(f"    Estado actual: {status_summary()}")

    start = time.time()
    try:
        if not SCRAPPER.exists():
            log(f"  ❌ No se encontró '{SCRAPPER}'. Abortando.")
            break

        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            [sys.executable, str(SCRAPPER)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SUBPROCESS_TIMEOUT,
            cwd=str(SCRIPT_DIR),
            env=child_env,
        )
        for line in result.stdout.splitlines():
            log(f"  {line}")
        if result.returncode != 0:
            log(f"  ⚠ Scrapper salió con código {result.returncode}")
            if result.stderr:
                for line in result.stderr.rstrip().splitlines():
                    log(f"  STDERR: {line}")
    except subprocess.TimeoutExpired:
        log("  ⚠ Scrapper excedió el timeout. Continuando...")
    except FileNotFoundError:
        log(f"  ❌ No se encontró '{SCRAPPER}'. Abortando.")
        break
    except Exception as e:
        log(f"  ❌ Error inesperado: {e}")

    elapsed = time.time() - start
    log(f"    Corrida tomó {elapsed/60:.1f} min")
    log(f"    Estado después: {status_summary()}")

    if FINISHED_FLAG.exists():
        log("Flag 'listing_finished.flag' detectado después de la corrida. Terminando.")
        break

    log(f"Durmiendo {INTERVAL_MINUTES} minutos...")
    time.sleep(INTERVAL_MINUTES * 60)

log("Auto-scraper-detalle finalizado.")
"""
scrapper_detalle.py - v4.1
Recorre el listado paginado de Inmuebles24 (Gustavo A. Madero),
extrae URLs de propiedades y enriquece cada una con datos de detalle.
Filtra solo propiedades habitacionales (casa/departamento/etc).
"""
import os
import re
import json
import base64
import random
from pathlib import Path
from time import sleep

import pandas as pd
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

# ============================================================
# CONFIG
# ============================================================
BASE_LISTING_URL = "https://www.inmuebles24.com/casas-en-venta-en-gustavo-a.-madero-incluir-comercializa-remates-publisher.html?utm_source=google&utm_medium=cpc&utm_campaign=Search_Sale_CMX-EMX_Tipo-inmueble_DSA&utm_content=Casas-CMX&gad_source=1"
REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = REPO_ROOT / "data" / "bronze"
OUTPUT_FILE = OUTPUT_DIR / "casas_gam_full.csv"
PROGRESS_FILE = OUTPUT_DIR / "progress_detalle.json"
PAGES_FILE = OUTPUT_DIR / "progress_pages.json"
FINISHED_FLAG = OUTPUT_DIR / "listing_finished.flag"

BATCH_SIZE = 40          # propiedades a procesar (detalle) por ejecución
MAX_LISTING_PAGES = 200  # tope de seguridad
CHROME_VERSION = None    # ej.: 124. Dejar None auto-detecta la versión instalada.
DEBUG = True
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def find_chrome_binary() -> str | None:
    """Return the full path to Chrome/Chromium if present; otherwise None."""
    candidates = []
    for env_name in ("CHROME_BIN", "GOOGLE_CHROME_BIN", "CHROMIUM_BIN", "CHROMIUM_BROWSER"):
        value = os.getenv(env_name)
        if value:
            candidates.append(value)

    if os.name == "nt":
        candidates.extend([
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Chromium\Application\chrome.exe",
            r"C:\Program Files (x86)\Chromium\Application\chrome.exe",
        ])
    else:
        candidates.extend([
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ])

    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return str(path)
    return None

# ============================================================
# SI YA SE TERMINÓ EL LISTADO, SALIR
# ============================================================
if FINISHED_FLAG.exists():
    print("Flag 'listing_finished.flag' presente. Nada que hacer.")
    raise SystemExit(0)

# ============================================================
# CARGAR PROGRESO DE URLs
# ============================================================
if PROGRESS_FILE.exists():
    with open(PROGRESS_FILE) as f:
        progress = json.load(f)
else:
    progress = {"done_urls": [], "failed_urls": [], "skipped_urls": []}

done_urls = set(progress.get("done_urls", []))
failed_urls = set(progress.get("failed_urls", []))
skipped_urls = set(progress.get("skipped_urls", []))

print(f"URLs done: {len(done_urls)} | skipped: {len(skipped_urls)} | failed: {len(failed_urls)}")

# ============================================================
# CARGAR PROGRESO DE PÁGINAS
# ============================================================
if PAGES_FILE.exists():
    with open(PAGES_FILE) as f:
        pages_data = json.load(f)
else:
    pages_data = {"done_pages": []}

done_pages = set(pages_data.get("done_pages", []))
print(f"Páginas completadas: {len(done_pages)} -> {sorted(done_pages)}")

# ============================================================
# DRIVER
# ============================================================
chrome_binary = find_chrome_binary()
if not chrome_binary:
    raise SystemExit(
        "No se encontró Chrome/Chromium instalado. Instala Chrome, o define CHROME_BIN "
        "con la ruta del navegador y vuelve a ejecutar el scraper."
    )

options = uc.ChromeOptions()
options.binary_location = chrome_binary
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

chrome_kwargs = {"options": options}
if CHROME_VERSION is not None:
    chrome_kwargs["version_main"] = int(CHROME_VERSION)

driver = uc.Chrome(**chrome_kwargs)

# ============================================================
# CARGA DE DATOS EXISTENTES
# ============================================================
if OUTPUT_FILE.exists():
    existing_df = pd.read_csv(OUTPUT_FILE)
    print(f"Filas ya enriquecidas en CSV: {len(existing_df)}")
else:
    existing_df = pd.DataFrame()

new_rows = []

# ============================================================
# FILTRO: solo propiedades habitacionales
# ============================================================
VALID_TYPES = {
    "Casa",
    "Casa en condominio",
    "Villa",
    "Quinta",
    "Departamento",
    "Departamento en condominio",
    "Apartamento",
    "Apartamento en condominio",
    "Dúplex",
    "Duplex",
    "PH",
    "Penthouse",
    "Loft",
    "Studio",
}
counters = {"saved": 0, "skipped": 0, "failed": 0}

# ============================================================
# HELPERS DE EXTRACCIÓN
# ============================================================
def extract_mainFeatures(html):
    m = re.search(r'const mainFeatures = (\{.*?\})\s*\n', html, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}


def num(val):
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    m = re.search(r"(\d+)", str(val))
    return int(m.group(1)) if m else 0


def parse_antiguedad(val):
    if val is None or val == "":
        return None
    s = str(val).lower()
    if any(k in s for k in ["construc", "preventa", "nueva", "estrenar"]):
        return 0
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None


def decode_b64(b64):
    try:
        return base64.b64decode(b64).decode("utf-8")
    except Exception:
        return None


def extract_page_data(html):
    d = {}

    # --- mainFeatures ---
    mf = extract_mainFeatures(html)
    d["Total_area_m2"] = num(mf.get("CFT100", {}).get("value"))
    d["Built_area_m2"] = num(mf.get("CFT101", {}).get("value"))
    d["Rooms"] = num(mf.get("CFT2", {}).get("value"))
    d["Bathrooms"] = num(mf.get("CFT3", {}).get("value"))
    d["HalfBathrooms"] = num(mf.get("CFT4", {}).get("value"))
    d["Parkings"] = num(mf.get("CFT7", {}).get("value"))
    d["Antiguedad"] = parse_antiguedad(mf.get("CFT5", {}).get("value"))
    d["Servicios"] = []

    # --- location ---
    m = re.search(r"'location':\s*(\{.*?\})\s*,\s*'description'", html, re.DOTALL)
    if m:
        try:
            loc = json.loads(m.group(1))
            d["Colonia"] = loc.get("name")
            p1 = loc.get("parent") or {}
            d["Alcaldia"] = p1.get("name")
            p2 = p1.get("parent") or {}
            d["Ciudad"] = p2.get("name")
            p3 = p2.get("parent") or {}
            d["Estado"] = p3.get("name")
        except json.JSONDecodeError:
            pass

    # --- price ---
    m = re.search(r"'price':\s*'MN\s*([\d,]+)'", html)
    if m:
        d["Price"] = int(m.group(1).replace(",", ""))
    else:
        m = re.search(r'"amount":(\d+)', html)
        if m:
            d["Price"] = int(m.group(1))

    # --- expenses ---
    m = re.search(r"'expenses':\s*'([\d.,]+)'", html)
    if m:
        try:
            d["Maintenance_cost"] = int(float(m.group(1).replace(",", "")))
        except ValueError:
            d["Maintenance_cost"] = 0
    else:
        d["Maintenance_cost"] = 0

    # --- address ---
    m = re.search(r"'address':\s*(\{.*?\})\s*,\s*'mapZoom'", html, re.DOTALL)
    if m:
        try:
            addr = json.loads(m.group(1))
            d["Address"] = addr.get("name")
        except json.JSONDecodeError:
            pass

    # --- realEstateType ---
    m = re.search(r"'realEstateType':\s*(\{[^}]+\})", html)
    if m:
        try:
            ret = json.loads(m.group(1))
            d["PropertyType"] = ret.get("name")
        except json.JSONDecodeError:
            pass

    # --- postingType ---
    m = re.search(r"'postingType':\s*'([^']+)'", html)
    if m:
        d["PostingType"] = m.group(1)

    # --- lat / lng ---
    m = re.search(r'const mapLatOf\s*=\s*"([^"]+)"', html)
    if m:
        lat = decode_b64(m.group(1))
        if lat:
            try:
                d["Latitude"] = float(lat)
            except ValueError:
                pass
    m = re.search(r'const mapLngOf\s*=\s*"([^"]+)"', html)
    if m:
        lng = decode_b64(m.group(1))
        if lng:
            try:
                d["Longitude"] = float(lng)
            except ValueError:
                pass

    # --- idAviso ---
    m = re.search(r"'idAviso':\s*'(\d+)'", html)
    if m:
        d["PostingID"] = m.group(1)

    # -- Services --
    m = re.search(r'"Servicios":\s*(\{(?:[^{}]*|\{[^{}]*\})*\})', html)
    if m:
        try:
            servicios_data = json.loads(m.group(1))
            for key, val in servicios_data.items():
                if isinstance(val, dict) and "label" in val:
                    d["Servicios"].append(val["label"])
        except json.JSONDecodeError:
            pass

    return d


# ============================================================
# HELPERS DE PERSISTENCIA
# ============================================================
def save_progress_urls():
    progress["done_urls"] = sorted(done_urls)
    progress["failed_urls"] = sorted(failed_urls)
    progress["skipped_urls"] = sorted(skipped_urls)
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def save_progress_pages():
    with open(PAGES_FILE, "w") as f:
        json.dump({"done_pages": sorted(done_pages)}, f, indent=2)


def save_csv():
    combined = pd.concat([existing_df, pd.DataFrame(new_rows)], ignore_index=True)
    combined = combined.drop_duplicates(subset=["URL"], keep="first")
    combined.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")


# ============================================================
# HELPERS DE LISTADO
# ============================================================
def listing_page_url(page: int) -> str:
    if page == 1:
        return BASE_LISTING_URL
    sep = "&" if "?" in BASE_LISTING_URL else "?"
    return f"{BASE_LISTING_URL}{sep}page={page}"


def extract_listing_urls(driver) -> set:
    """Devuelve set de URLs limpias (/propiedades/...) visibles en la página."""
    enlaces = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/propiedades/"]')
    urls = set()
    for a in enlaces:
        href = a.get_attribute("href")
        if not href:
            continue
        clean = href.split("?")[0]
        if "/propiedades/" in clean:
            urls.add(clean)
    return urls


def page_has_pending(urls_pagina: set) -> list:
    """Lista de URLs de la página que aún no están resueltas."""
    return [
        u for u in urls_pagina
        if u not in done_urls and u not in failed_urls and u not in skipped_urls
    ]


# ============================================================
# LOOP PRINCIPAL
# ============================================================
page = 1
while page in done_pages:
    page += 1

print(f"\nPágina inicial a procesar: {page}")
processed_this_run = 0

try:
    while page <= MAX_LISTING_PAGES and processed_this_run < BATCH_SIZE:
        print(f"\n{'=' * 50}")
        print(f"[LISTADO] Página {page}: {listing_page_url(page)}")
        print(f"{'=' * 50}")

        try:
            driver.get(listing_page_url(page))
            sleep(random.uniform(4, 7))
        except Exception as e:
            print(f"  → Error abriendo listado: {e}")
            break

        # Cloudflare check
        title = driver.title
        if "Attention Required" in title or "Just a moment" in title:
            print("  → Cloudflare bloqueó el listado. Deteniendo corrida.")
            break

        # Extraer URLs
        try:
            urls_pagina = extract_listing_urls(driver)
        except Exception as e:
            print(f"  → Error extrayendo URLs del listado: {e}")
            break

        if not urls_pagina:
            print("  → Página sin propiedades. Fin del listado.")
            FINISHED_FLAG.write_text("done", encoding="utf-8")
            break

        pendientes = page_has_pending(urls_pagina)
        print(f"  URLs en página: {len(urls_pagina)} | pendientes: {len(pendientes)}")

        # Procesar pendientes hasta agotar batch
        for i, url in enumerate(pendientes, 1):
            if processed_this_run >= BATCH_SIZE:
                print("  → Batch completo. Se continúa en la próxima corrida.")
                break

            print(f"\n  [{processed_this_run + 1}/{BATCH_SIZE}] {url[:100]}...")

            try:
                driver.get(url)
                sleep(random.uniform(4, 7))

                t = driver.title
                if "Attention Required" in t or "Just a moment" in t:
                    print("    → Cloudflare en detalle. Deteniendo.")
                    raise KeyboardInterrupt("Cloudflare")

                html = driver.page_source
                if "const mainFeatures" not in html:
                    print("    → Sin mainFeatures. Marcada como fallida.")
                    failed_urls.add(url)
                    counters["failed"] += 1
                    processed_this_run += 1
                    save_progress_urls()
                    continue

                row = extract_page_data(html)
                property_type = row.get("PropertyType")

                # Filtro habitacional
                if property_type not in VALID_TYPES:
                    print(f"    → OMITIDA: tipo '{property_type}'")
                    skipped_urls.add(url)
                    counters["skipped"] += 1
                    processed_this_run += 1
                    save_progress_urls()
                    continue

                row["URL"] = url
                new_rows.append(row)
                done_urls.add(url)
                counters["saved"] += 1
                processed_this_run += 1

                print(f"    → OK. ${row.get('Price', 0):,} | "
                      f"{property_type} | "
                      f"Terr {row.get('Total_area_m2', 0)} | "
                      f"Cons {row.get('Built_area_m2', 0)} | "
                      f"{row.get('Colonia', '?')} | "
                      f"Ant {row.get('Antiguedad')}")

                # Guardado parcial cada 5
                if counters["saved"] % 5 == 0:
                    save_progress_urls()
                    save_csv()

                sleep(random.uniform(3, 6))

            except KeyboardInterrupt:
                print("    → Interrupción. Guardando y saliendo.")
                save_progress_urls()
                save_csv()
                raise
            except Exception as e:
                print(f"    → Error: {e}")
                failed_urls.add(url)
                counters["failed"] += 1
                processed_this_run += 1
                save_progress_urls()

        # Re-evaluar si la página quedó 100% resuelta
        pendientes_restantes = page_has_pending(urls_pagina)
        if not pendientes_restantes:
            done_pages.add(page)
            save_progress_pages()
            print(f"\n  ✅ Página {page} COMPLETA. Marcada como done.")
            page += 1
        else:
            print(f"\n  ⏸ Página {page} aún tiene {len(pendientes_restantes)} pendientes.")
            print(f"     Se continuará en la próxima corrida.")
            break  # no avanzar de página

except KeyboardInterrupt:
    print("\nInterrupción manual detectada. Guardando estado...")

finally:
    # Guardado final
    save_progress_urls()
    save_progress_pages()
    save_csv()
    try:
        driver.quit()
    except Exception:
        pass

print(f"\n{'=' * 50}")
print(f"Corrida terminada.")
print(f"  Guardadas (casa/dpto): {counters['saved']}")
print(f"  Omitidas (no habit.):  {counters['skipped']}")
print(f"  Fallidas:              {counters['failed']}")
print(f"  ---")
print(f"  Total URLs done:       {len(done_urls)}")
print(f"  Total omitidas:        {len(skipped_urls)}")
print(f"  Total fallidas:        {len(failed_urls)}")
print(f"  Páginas completas:     {len(done_pages)}")
print(f"  CSV: {OUTPUT_FILE}")
print(f"{'=' * 50}")
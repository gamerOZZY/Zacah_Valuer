"""
test_url.py
Prueba rápida: visita una URL y muestra todo lo que se extrae.
Uso:
    python3 test_url.py                          # usa la URL por defecto
    python3 test_url.py "https://..."            # usa tu URL
"""
import sys
import base64
import json
import re
from time import sleep

import undetected_chromedriver as uc


# ============================================================
# URL A PROBAR
# ============================================================
DEFAULT_URL = "https://www.inmuebles24.com/casas-en-venta-en-gustavo-a.-madero-incluir-comercializa-remates-publisher.html?utm_source=google&utm_medium=cpc&utm_campaign=Search_Sale_CMX-EMX_Tipo-inmueble_DSA&utm_content=Casas-CMX&gad_source=1"

URL = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL


# ============================================================
# FUNCIONES DE EXTRACCIÓN (iguales al scraper)
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

    # --- realEstateType (regex robusto) ---
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

    # --- lat / lng (base64, tolera espacios variables) ---
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

    return d


# ============================================================
# MAIN
# ============================================================
print("=" * 70)
print("PRUEBA DE EXTRACCIÓN DE UNA URL")
print("=" * 70)
print(f"URL: {URL}\n")

options = uc.ChromeOptions()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = uc.Chrome(options=options)

try:
    print("Abriendo página...")
    driver.get(URL)
    sleep(6)

    print(f"Título: {driver.title}\n")

    html = driver.page_source

    # Verificar que los bloques clave están
    has_mainfeatures = "const mainFeatures" in html
    has_location     = "'location':" in html
    has_price        = "'price':" in html
    has_type         = "'realEstateType':" in html
    has_lat          = "const mapLatOf" in html

    print("--- Bloques detectados en el HTML ---")
    print(f"  'const mainFeatures' presente: {has_mainfeatures}")
    print(f"  'location' presente:            {has_location}")
    print(f"  'price' presente:               {has_price}")
    print(f"  'realEstateType' presente:      {has_type}")
    print(f"  'const mapLatOf' presente:      {has_lat}")
    print()

    # Extraer
    row = extract_page_data(html)

    print("--- Datos extraídos ---")
    if not row:
        print("  ¡NADA! La extracción falló.")
    else:
        for k, v in row.items():
            print(f"  {k:<20} = {v}")

    print()

    # Validar tipo de propiedad
    VALID_TYPES = {
        "Casa", "Departamento",
        "Casa en condominio", "Departamento en condominio",
        "Dúplex", "Duplex", "PH", "Penthouse",
        "Villa", "Quinta", "Loft", "Studio",
    }
    ptype = row.get("PropertyType")
    if ptype in VALID_TYPES:
        print(f"✅ TIPO VÁLIDO: '{ptype}' → se guardaría")
    else:
        print(f"❌ TIPO INVÁLIDO: '{ptype}' → se omitiría")

    # Resumen final
    print()
    print("=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"  Precio:       ${row.get('Price', 0):,}")
    print(f"  Tipo:         {row.get('PropertyType', '?')}")
    print(f"  Colonia:      {row.get('Colonia', '?')}")
    print(f"  Alcaldía:     {row.get('Alcaldia', '?')}")
    print(f"  Terreno:      {row.get('Total_area_m2', 0)} m²")
    print(f"  Construido:   {row.get('Built_area_m2', 0)} m²")
    print(f"  Recámaras:    {row.get('Rooms', 0)}")
    print(f"  Baños:        {row.get('Bathrooms', 0)}")
    print(f"  Medios baños: {row.get('HalfBathrooms', 0)}")
    print(f"  Estac.:       {row.get('Parkings', 0)}")
    print(f"  Antigüedad:   {row.get('Antiguedad', '?')} años")
    print(f"  Lat/Lng:      {row.get('Latitude', '?')}, {row.get('Longitude', '?')}")
    print("=" * 70)

finally:
    driver.quit()
from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
CSV_PATH = REPO_ROOT / "data" / "bronze" / "casas_gam_full.csv"
if not CSV_PATH.exists():
    legacy_path = REPO_ROOT / "data" / "bronze" / "casas_gam.csv"
    if legacy_path.exists():
        CSV_PATH = legacy_path
    else:
        raise FileNotFoundError(f"No se encontró el CSV en {CSV_PATH}")

df = pd.read_csv(CSV_PATH)
print(f"Total filas: {len(df)}")
print(f"Con URL: {df['URL'].notna().sum()}")
print(f"Con URL de /propiedades/: {df['URL'].str.contains('/propiedades/', na=False).sum()}")
print(f"URLs únicas: {df['URL'].dropna().nunique()}")
print()
print("Ejemplos:")
for u in df[df['URL'].str.contains('/propiedades/', na=False)]['URL'].head(3):
    print(f"  {u}")
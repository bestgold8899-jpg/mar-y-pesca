
import json
from pathlib import Path

import xarray as xr

input_file = Path("prueba_dakhla_global.nc")
output_file = Path("oleaje_dakhla.json")

if not input_file.exists():
    raise FileNotFoundError(
        f"No se encuentra el archivo: {input_file}"
    )

ds = xr.open_dataset(input_file)

required_variables = ["VHM0", "VMDR", "VTPK"]

for variable in required_variables:
    if variable not in ds:
        raise ValueError(f"Falta la variable {variable}")

df = ds[required_variables].to_dataframe().dropna()
df = df.reset_index()

records = []

for _, row in df.iterrows():
    records.append({
        "fecha_utc": str(row["time"]),
        "latitud": round(float(row["latitude"]), 5),
        "longitud": round(float(row["longitude"]), 5),
        "altura_olas_m": round(float(row["VHM0"]), 2),
        "direccion_olas_grados": round(float(row["VMDR"]), 1),
        "periodo_olas_s": round(float(row["VTPK"]), 2)
    })

result = {
    "localidad": "Dakhla",
    "fuente": "Copernicus Marine Global Waves",
    "numero_registros": len(records),
    "datos": records
}

with output_file.open("w", encoding="utf-8") as file:
    json.dump(result, file, ensure_ascii=False, indent=2)

ds.close()

print(f"Procesamiento correcto: {len(records)} registros")
print(f"Archivo generado: {output_file}")

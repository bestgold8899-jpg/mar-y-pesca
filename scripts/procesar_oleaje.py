
import argparse
import json
import math
from pathlib import Path

import pandas as pd
import xarray as xr


def haversine_km(lat1, lon1, lat2, lon2):
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2)
        * math.sin(dlambda / 2) ** 2
    )

    return 2 * radius_km * math.asin(math.sqrt(a))


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--lat", required=True, type=float)
    parser.add_argument("--lon", required=True, type=float)

    args = parser.parse_args()

    input_file = Path(args.input)
    output_file = Path(args.output)

    if not input_file.exists():
        raise FileNotFoundError(
            f"No se encuentra el archivo: {input_file}"
        )

    required_variables = ["VHM0", "VMDR", "VTPK"]

    with xr.open_dataset(input_file) as ds:
        for variable in required_variables:
            if variable not in ds.variables:
                raise ValueError(
                    f"Falta la variable {variable}"
                )

        df = ds[required_variables].to_dataframe().reset_index()

    required_columns = [
        "time",
        "latitude",
        "longitude",
        *required_variables
    ]

    missing = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            "Faltan columnas: " + ", ".join(missing)
        )

    df = df.dropna(
        subset=required_variables
        + ["time", "latitude", "longitude"]
    )

    if df.empty:
        raise ValueError(
            f"No hay datos oceánicos válidos para {args.location}"
        )

    # Buscar el punto marino válido más cercano.
    points = df[
        ["latitude", "longitude"]
    ].drop_duplicates().copy()

    points["distancia_km"] = points.apply(
        lambda point: haversine_km(
            args.lat,
            args.lon,
            float(point["latitude"]),
            float(point["longitude"])
        ),
        axis=1
    )

    nearest = points.sort_values(
        "distancia_km"
    ).iloc[0]

    selected_lat = float(nearest["latitude"])
    selected_lon = float(nearest["longitude"])
    distance_km = float(nearest["distancia_km"])

    # No asignar datos de un punto demasiado lejano.
    if distance_km > 30:
        raise ValueError(
            f"El punto marino más cercano a {args.location} "
            f"está a {distance_km:.1f} km. "
            "Se cancela para evitar datos engañosos."
        )

    selected = df[
        (df["latitude"] == selected_lat)
        & (df["longitude"] == selected_lon)
    ].sort_values("time")

    records = []

    for _, row in selected.iterrows():
        timestamp = pd.Timestamp(row["time"])

        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")

        records.append({
            "fecha_utc": timestamp.isoformat().replace(
                "+00:00", "Z"
            ),
            "latitud": round(selected_lat, 5),
            "longitud": round(selected_lon, 5),
            "altura_olas_m": round(
                float(row["VHM0"]), 2
            ),
            "direccion_olas_grados": round(
                float(row["VMDR"]) % 360, 1
            ) % 360,
            "periodo_olas_s": round(
                float(row["VTPK"]), 2
            )
        })

    if not records:
        raise ValueError(
            f"No se pudieron preparar registros para {args.location}"
        )

    result = {
        "localidad": args.location,
        "fuente": "Copernicus Marine Global Waves",
        "numero_registros": len(records),
        "punto_maritimo": {
            "latitud": round(selected_lat, 5),
            "longitud": round(selected_lon, 5),
            "distancia_a_localidad_km": round(
                distance_km, 2
            )
        },
        "datos": records
    }

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"Correcto: {args.location} | "
        f"{len(records)} registros | "
        f"Distancia: {distance_km:.2f} km"
    )

    print(f"JSON generado: {output_file}")


if __name__ == "__main__":
    main()

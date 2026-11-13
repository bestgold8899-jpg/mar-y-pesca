
#!/usr/bin/env python3
"""Convierte el NetCDF OSTIA/Copernicus en JSON para Mar & Pesca."""

import sys
import json
import math
import re
from datetime import datetime, timezone, timedelta

import h5py
import numpy as np


LOCATIONS = {
    "mdiq": {"name": "M'diq", "lat": 35.684, "lng": -5.326},
    "martil": {"name": "Martil", "lat": 35.617, "lng": -5.275},
    "fnideq": {"name": "Fnideq / Castillejos", "lat": 35.849, "lng": -5.357},
    "tanger": {"name": "Tánger", "lat": 35.779, "lng": -5.813},
    "al-hoceima": {"name": "Al Hoceima", "lat": 35.249, "lng": -3.937},
    "nador": {"name": "Nador", "lat": 35.168, "lng": -2.928},
    "casablanca": {"name": "Casablanca", "lat": 33.599, "lng": -7.620},
    "agadir": {"name": "Agadir", "lat": 30.427, "lng": -9.598},
    "dakhla": {"name": "Dakhla", "lat": 23.684, "lng": -15.958},
    "asilah": {"name": "Asilah", "lat": 35.465, "lng": -6.034},
    "larache": {"name": "Larache", "lat": 35.193, "lng": -6.156},
    "mehdia": {"name": "Mehdia", "lat": 34.256, "lng": -6.672},
    "el-jadida": {"name": "El Jadida", "lat": 33.256, "lng": -8.508},
    "safi": {"name": "Safi", "lat": 32.299, "lng": -9.237},
    "essaouira": {"name": "Essaouira", "lat": 31.513, "lng": -9.770},
    "sidi-ifni": {"name": "Sidi Ifni", "lat": 29.379, "lng": -10.173},
    "tan-tan-plage": {"name": "Tan-Tan Plage (El Ouatia)", "lat": 28.493, "lng": -11.337},
    "tarfaya": {"name": "Tarfaya", "lat": 27.937, "lng": -12.927},
    "laayoune-plage": {"name": "Laayoune Plage (Foum El Oued)", "lat": 27.100, "lng": -13.430},
    "saidia": {"name": "Saïdia", "lat": 35.081, "lng": -2.230},
}

MAX_DISTANCE_KM = 25.0


def decode_text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def attribute_numbers(value):
    """Convierte atributos escalares o arrays en una lista de números."""
    if value is None:
        return []

    array = np.asarray(value).reshape(-1)
    result = []

    for item in array:
        try:
            number = float(item)
            if math.isfinite(number):
                result.append(number)
        except (TypeError, ValueError):
            continue

    return result


def read_valid_time(time_dataset):
    """Interpreta la fecha utilizando las unidades declaradas en NetCDF."""
    raw_time = float(np.asarray(time_dataset[-1]).item())

    units = time_dataset.attrs.get("units")
    if units is None:
        raise SystemExit("La variable time no contiene el atributo units.")

    units = decode_text(units)

    match = re.match(
        r"^\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?)\s+since\s+(.+?)\s*$",
        units,
        re.IGNORECASE,
    )

    if not match:
        raise SystemExit(f"Unidades de tiempo no reconocidas: {units}")

    unit = match.group(1).lower()
    origin_text = match.group(2).strip()

    if origin_text.endswith("Z"):
        origin_text = origin_text[:-1] + "+00:00"

    try:
        origin = datetime.fromisoformat(origin_text)
    except ValueError:
        raise SystemExit(f"Fecha de origen no reconocida: {origin_text}")

    if origin.tzinfo is None:
        origin = origin.replace(tzinfo=timezone.utc)
    else:
        origin = origin.astimezone(timezone.utc)

    if unit.startswith(("second", "sec")):
        delta = timedelta(seconds=raw_time)
    elif unit.startswith(("minute", "min")):
        delta = timedelta(minutes=raw_time)
    elif unit.startswith(("hour", "hr")):
        delta = timedelta(hours=raw_time)
    elif unit.startswith("day"):
        delta = timedelta(days=raw_time)
    else:
        raise SystemExit(f"Unidad de tiempo no soportada: {unit}")

    return origin + delta


def normalize_longitude(longitude):
    return ((longitude + 180.0) % 360.0) - 180.0


def nearest_ocean_pixel(lat_grid, lon_grid, sst, target_lat, target_lng):
    """Busca el píxel oceánico válido más cercano a una localidad."""

    lat_idx = np.where(np.abs(lat_grid - target_lat) <= 0.5)[0]

    lon_difference = (
        (lon_grid - target_lng + 180.0) % 360.0
    ) - 180.0

    lon_idx = np.where(np.abs(lon_difference) <= 0.5)[0]

    if not len(lat_idx) or not len(lon_idx):
        return None

    lats = lat_grid[lat_idx][:, None]
    lons = lon_grid[lon_idx][None, :]

    values = sst[np.ix_(lat_idx, lon_idx)]

    lat1 = np.radians(target_lat)
    lat2 = np.radians(lats)

    dlat = lat2 - lat1
    dlon = np.radians(
        ((lons - target_lng + 180.0) % 360.0) - 180.0
    )

    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    )

    distance = 6371.0 * 2.0 * np.arcsin(
        np.sqrt(np.clip(a, 0.0, 1.0))
    )

    distance = np.where(np.isfinite(values), distance, np.inf)

    idx = np.unravel_index(np.argmin(distance), distance.shape)
    km = float(distance[idx])

    if not math.isfinite(km) or km > MAX_DISTANCE_KM:
        return None

    kelvin = float(values[idx])
    celsius = kelvin - 273.15

    pixel_lat = float(lats[idx[0], 0])
    pixel_lng = normalize_longitude(float(lons[0, idx[1]]))

    return {
        "temperature_c": round(celsius, 2),
        "temperature_k": round(kelvin, 2),
        "pixel": {
            "lat": round(pixel_lat, 5),
            "lng": round(pixel_lng, 5),
        },
        "distance_km": round(km, 2),
    }


def main():
    if len(sys.argv) < 2:
        raise SystemExit(
            "Uso: python scripts/procesar_sst.py archivo.nc [salida.json]"
        )

    source = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "sst_mar.json"

    with h5py.File(source, "r") as nc:

        required = ("analysed_sst", "latitude", "longitude", "time")

        for name in required:
            if name not in nc:
                raise SystemExit(f"Falta la variable requerida: {name}")

        dataset = nc["analysed_sst"]

        if dataset.ndim != 3:
            raise SystemExit(
                f"Dimensiones SST inesperadas: {dataset.shape}. "
                "Se esperaba [tiempo, latitud, longitud]."
            )

        raw = np.asarray(dataset[-1], dtype=np.float64)

        # Detectar valores de relleno, aunque el atributo sea un array.
        fill_values = []
        fill_values.extend(
            attribute_numbers(dataset.attrs.get("_FillValue"))
        )
        fill_values.extend(
            attribute_numbers(dataset.attrs.get("missing_value"))
        )

        for fill_value in fill_values:
            raw[raw == fill_value] = np.nan

        # Aplicar escala y desplazamiento si el NetCDF los declara.
        scale_values = attribute_numbers(
            dataset.attrs.get("scale_factor")
        )
        offset_values = attribute_numbers(
            dataset.attrs.get("add_offset")
        )

        scale = scale_values[0] if scale_values else 1.0
        offset = offset_values[0] if offset_values else 0.0

        raw = raw * scale + offset

        lat = np.asarray(nc["latitude"][:], dtype=np.float64).squeeze()
        lon = np.asarray(nc["longitude"][:], dtype=np.float64).squeeze()

        if lat.ndim != 1 or lon.ndim != 1:
            raise SystemExit(
                "Las coordenadas latitude y longitude deben ser "
                "arrays de una dimensión."
            )

        if raw.shape != (len(lat), len(lon)):
            raise SystemExit(
                f"Dimensiones incompatibles: SST {raw.shape}, "
                f"latitud {len(lat)}, longitud {len(lon)}."
            )

        # Convertir la fecha usando las unidades reales del NetCDF.
        valid_datetime = read_valid_time(nc["time"])
        valid_time = valid_datetime.date().isoformat()

        age_days = (
            datetime.now(timezone.utc).date() - valid_datetime.date()
        ).days

        if age_days < 0:
            raise SystemExit(
                f"La fecha SST está en el futuro: {valid_time}"
            )

        if age_days > 4:
            raise SystemExit(
                f"SST demasiado antigua: {valid_time} "
                f"({age_days} días). No se enviará al Worker."
            )

        locations = {}

        for slug, place in LOCATIONS.items():
            result = nearest_ocean_pixel(
                lat,
                lon,
                raw,
                place["lat"],
                place["lng"],
            )

            if result:
                locations[slug] = {
                    "name": place["name"],
                    **result,
                }
            else:
                locations[slug] = {
                    "name": place["name"],
                    "temperature_c": None,
                    "temperature_k": None,
                    "pixel": None,
                    "distance_km": None,
                }

        payload = {
            "ok": True,
            "source": "Copernicus Marine — METOFFICE OSTIA SST L4",
            "product": "SST_GLO_SST_L4_NRT_OBSERVATIONS_010_001",
            "dataset": "METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2",
            "date": valid_time,
            "variable": "analysed_sst",
            "unit": "°C",
            "conversion": "Kelvin - 273.15",
            "max_pixel_distance_km": MAX_DISTANCE_KM,
            "locations": locations,
        }

    with open(output, "w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    import os

    print(
        f"OK: {output} ({os.path.getsize(output)} bytes), "
        f"fecha {valid_time}"
    )

    for slug, item in locations.items():
        print(
            f"{slug}: {item['temperature_c']} °C; "
            f"distancia {item['distance_km']} km"
        )


if __name__ == "__main__":
    main()

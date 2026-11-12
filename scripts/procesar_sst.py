#!/usr/bin/env python3
"""Convierte el NetCDF OSTIA/Copernicus en JSON ligero para Mar & Pesca.
Uso: python scripts/procesar_sst.py archivo.nc [salida.json]
Requiere: h5py, numpy
"""
import sys, json, math
from datetime import datetime, timezone
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
}
MAX_DISTANCE_KM = 25.0


def nearest_ocean_pixel(lat_grid, lon_grid, sst, target_lat, target_lng):
    # Recorte local para evitar recorrer todo el dominio en cada localidad.
    lat_idx = np.where(np.abs(lat_grid - target_lat) <= 0.5)[0]
    lon_idx = np.where(np.abs(lon_grid - target_lng) <= 0.5)[0]
    if not len(lat_idx) or not len(lon_idx):
        return None
    lats = lat_grid[lat_idx][:, None]
    lons = lon_grid[lon_idx][None, :]
    values = sst[np.ix_(lat_idx, lon_idx)]
    lat1 = np.radians(target_lat)
    lat2 = np.radians(lats)
    dlat = lat2 - lat1
    dlon = np.radians(lons - target_lng)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    distance = 6371.0 * 2 * np.arcsin(np.sqrt(a))
    distance = np.where(np.isfinite(values), distance, np.inf)
    idx = np.unravel_index(np.argmin(distance), distance.shape)
    km = float(distance[idx])
    if not math.isfinite(km) or km > MAX_DISTANCE_KM:
        return None
    kelvin = float(values[idx])
    celsius = kelvin - 273.15
    return {
        "temperature_c": round(celsius, 2),
        "temperature_k": round(kelvin, 2),
        "pixel": {"lat": round(float(lats[idx[0], 0]), 5), "lng": round(float(lons[0, idx[1]]), 5)},
        "distance_km": round(km, 2),
    }


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python procesar_sst.py archivo.nc [salida.json]")
    source = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "sst_mar.json"
    with h5py.File(source, "r") as nc:
        for required in ("analysed_sst", "latitude", "longitude", "time"):
            if required not in nc:
                raise SystemExit(f"Falta la variable requerida: {required}")
        raw = nc["analysed_sst"][-1].astype("float64")
        fill = nc["analysed_sst"].attrs.get("_FillValue")
        if fill is not None and np.isfinite(fill):
            raw[raw == float(fill)] = np.nan
        lat = nc["latitude"][:]
        lon = nc["longitude"][:]
        timestamp = float(nc["time"][-1])
        valid_datetime = datetime.fromtimestamp(timestamp, timezone.utc)
        valid_time = valid_datetime.date().isoformat()
        age_days = (datetime.now(timezone.utc).date() - valid_datetime.date()).days
        if age_days < 0:
            raise SystemExit(f"La fecha SST está en el futuro: {valid_time}")
        if age_days > 4:
            raise SystemExit(f"SST demasiado antigua: {valid_time} ({age_days} días). No se enviará al Worker.")
        locations = {}
        for slug, place in LOCATIONS.items():
            result = nearest_ocean_pixel(lat, lon, raw, place["lat"], place["lng"])
            if result:
                locations[slug] = {"name": place["name"], **result}
            else:
                locations[slug] = {"name": place["name"], "temperature_c": None, "temperature_k": None, "pixel": None, "distance_km": None}
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
    with open(output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {output} ({__import__('os').path.getsize(output)} bytes), fecha {valid_time}")
    for slug, item in locations.items():
        print(f"{slug}: {item['temperature_c']} °C; distancia {item['distance_km']} km")

if __name__ == "__main__":
    main()


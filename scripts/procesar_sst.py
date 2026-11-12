        fill = nc["analysed_sst"].attrs.get("_FillValue")
        if fill is not None:
            # NetCDF puede guardar _FillValue como escalar o como array.
            fill_values = np.asarray(fill, dtype="float64").ravel()
            fill_values = fill_values[np.isfinite(fill_values)]
            if fill_values.size:
                raw[np.isin(raw, fill_values)] = np.nan
        lat = nc["latitude"][:]
        lon = nc["longitude"][:]
        timestamp = float(nc["time"][0])
        valid_time = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
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

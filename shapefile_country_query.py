import geopandas as gpd

# Path to the shapefile
shapefile_path = "./ne_110m_admin_0_countries.shp"

# Load the shapefile with geopandas
world = gpd.read_file(shapefile_path)

# Loop through each country entry
print("🌍 Country Info (Name, Bounding Box, Approx. Main Point):\n")
for idx, row in world.iterrows():
    country_name = row['NAME']
    geometry = row['geometry']

    # Calculate bounding box: [minx, miny, maxx, maxy]
    minx, miny, maxx, maxy = geometry.bounds

    # Get a "main city" approximation via representative_point or centroid
    if geometry.geom_type == 'MultiPolygon':
        main_point = geometry.representative_point()
    else:
        main_point = geometry.centroid

    print(f"🔹 Country: {country_name}")
    print(f"   🧭 Bounding Box:")
    print(f"      min_lng: {minx:.4f}, min_lat: {miny:.4f}")
    print(f"      max_lng: {maxx:.4f}, max_lat: {maxy:.4f}")
    print(f"   🏙️  Approx. Main Point: lat={main_point.y:.4f}, lng={main_point.x:.4f}")
    print("-" * 50)

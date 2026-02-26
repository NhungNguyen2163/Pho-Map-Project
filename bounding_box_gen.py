import geopandas as gpd
from shapely.geometry import Point
from geopy.distance import distance
from geopy.point import Point as GeoPoint
import csv

# ---- Configuration ----
SHAPEFILE = "ne_110m_admin_0_countries.shp"  # Adjust if needed
COUNTRY_NAME = "Spain"                       # Change to test different country
STEP_KM = 10                                 # Grid spacing in kilometers
OUTPUT_CSV = "grid_points_output.csv"

# ---- Helper Function ----
def move_point(lat, lng, bearing, distance_km):
    origin = GeoPoint(lat, lng)
    destination = distance(kilometers=distance_km).destination(origin, bearing)
    return destination.latitude, destination.longitude

def generate_grid(min_lng, min_lat, max_lng, max_lat, step_km, country_polygon):
    points = []
    lat = min_lat
    while lat < max_lat:
        lng = min_lng
        while lng < max_lng:
            candidate_point = Point(lng, lat)
            if country_polygon.contains(candidate_point):
                points.append((lat, lng))
            _, lng = move_point(lat, lng, 90, step_km)  # Move East
        lat, _ = move_point(lat, lng, 0, step_km)       # Move North
    return points

# ---- Main Execution ----
def main():
    world = gpd.read_file(SHAPEFILE)
    country = world[world['NAME'] == COUNTRY_NAME]

    if country.empty:
        print(f"❌ Country '{COUNTRY_NAME}' not found.")
        return

    geometry = country.geometry.values[0]
    minx, miny, maxx, maxy = country.total_bounds

    print(f"🔲 Bounding box for {COUNTRY_NAME}:")
    print(f"   min_lng: {minx}, min_lat: {miny}")
    print(f"   max_lng: {maxx}, max_lat: {maxy}")

    grid_points = generate_grid(minx, miny, maxx, maxy, STEP_KM, geometry)
    
    print(f"📍 Generated {len(grid_points)} grid points inside {COUNTRY_NAME}.")
    print("🧮 Sample points:")
    for i, (lat, lng) in enumerate(grid_points[:10]):
        print(f"   {i+1}: lat={lat:.5f}, lng={lng:.5f}")

    # Optional: Save to CSV
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["latitude", "longitude"])
        writer.writerows(grid_points)
    print(f"📁 Grid points saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()

import requests
import time
import csv
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from geopy.distance import distance
from geopy.point import Point as GeoPoint
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster
from shapely.geometry import Point

# ------------------ CONFIGURATION ------------------
API_KEY = "AIzaSyCTjtSA9FFvimnpHi-tN2CelSKViQtYi-Y"
SEARCH_QUERY = "vietnamese restaurant"
GRID_STEP_KM = 10
RADIUS_METERS = 10000
API_QUOTA_LIMIT = 100000
WARNING_THRESHOLD = 0.8
COUNTRIES = [
    "England",
    "France",
    "Germany",
    "Poland",
    "Czech Republic",
    "Slovakia",
    "Italy",
    "Spain",
    "Portugal",
    "Belgium",
    "Netherlands",
    "Sweden",
    "Denmark",
    "Hungary",
    "Austria"
]

FIELDS = [
    "name", "address", "country", "phone", "website", "facebook", "instagram", "x_twitter",
    "price_level", "menu_url", "description", "latitude", "longitude",
    "google_maps_link", "google_share_link", "google_review_link"
]

api_request_count = 0
restaurant_collected_count = 0
seen_place_ids = set()
all_data = []
os.makedirs("Raw data", exist_ok=True)

# ------------------ HELPER FUNCTIONS ------------------

def move_point(lat, lng, bearing, distance_km):
    origin = GeoPoint(lat, lng)
    destination = distance(kilometers=distance_km).destination(origin, bearing)
    return destination.latitude, destination.longitude

def get_country_bounds_and_shape(country_name):
    shapefile_path = "./ne_110m_admin_0_countries.shp"
    world = gpd.read_file(shapefile_path)
    country = world[world['NAME'] == country_name]
    if country.empty:
        raise ValueError(f"Country '{country_name}' not found.")
    bounds = country.total_bounds  # [minx, miny, maxx, maxy]
    return bounds, country.geometry.values[0]

def generate_grid_within_country(min_lng, min_lat, max_lng, max_lat, step_km, country_polygon):
    points = []
    lat = min_lat
    while lat < max_lat:
        lng = min_lng
        while lng < max_lng:
            candidate_point = Point(lng, lat)
            if country_polygon.contains(candidate_point):
                points.append((lat, lng))
            _, lng = move_point(lat, lng, 90, step_km)  # East
        lat, _ = move_point(lat, lng, 0, step_km)  # North
    return points

def extract_social_links(website_url):
    if not website_url:
        return None, None, None
    try:
        response = requests.get(website_url, timeout=5)
        html = response.text
        facebook = re.search(r'href=["\']?(https?://[^"\'>]*facebook\\.com[^"\'>]*)', html)
        instagram = re.search(r'href=["\']?(https?://[^"\'>]*instagram\\.com[^"\'>]*)', html)
        x_twitter = re.search(r'href=["\']?(https?://[^"\'>]*(twitter\\.com|x\\.com)[^"\'>]*)', html)
        return (
            facebook.group(1) if facebook else None,
            instagram.group(1) if instagram else None,
            x_twitter.group(1) if x_twitter else None
        )
    except Exception as e:
        print(f"⚠️ Failed to extract social links: {e}")
        return None, None, None

def extract_menu_and_description(website_url):
    if not website_url:
        return None, None
    try:
        res = requests.get(website_url, timeout=7)
        soup = BeautifulSoup(res.text, 'html.parser')
        meta_desc = soup.find("meta", attrs={"name": "description"}) or \
                    soup.find("meta", attrs={"property": "og:description"})
        desc = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else None
        if not desc:
            paragraphs = soup.find_all(["section", "div", "p"])
            candidates = [tag.get_text(strip=True) for tag in paragraphs if len(tag.get_text(strip=True)) > 50]
            desc = candidates[0][:300] + "..." if candidates else None
        menu_link = None
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if any(word in href for word in ['menu', 'thucdon']) or 'menu' in (a.text or '').lower():
                menu_link = urljoin(website_url, a['href'])
                break
        return menu_link, desc
    except Exception as e:
        print(f"⚠️ Failed to extract menu or description: {e}")
        return None, None

def fetch_place_details(place_id, lat, lng, country):
    global api_request_count, restaurant_collected_count
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "key": API_KEY,
        "fields": "name,formatted_address,formatted_phone_number,website,price_level,url"
    }
    response = requests.get(url, params=params).json()
    api_request_count += 1
    if response.get("status") != "OK":
        print(f"❌ Error fetching details for {place_id}: {response.get('status')}")
        return None
    result = response.get("result", {})
    website = result.get("website")
    facebook, instagram, x_twitter = extract_social_links(website)
    menu_url, description = extract_menu_and_description(website)
    restaurant_collected_count += 1
    return {
        "name": result.get("name"),
        "address": result.get("formatted_address"),
        "country": country,
        "phone": result.get("formatted_phone_number"),
        "website": website,
        "facebook": facebook,
        "instagram": instagram,
        "x_twitter": x_twitter,
        "price_level": result.get("price_level"),
        "menu_url": menu_url,
        "description": description or f"{result.get('name')} located in {result.get('formatted_address')}",
        "latitude": lat,
        "longitude": lng,
        "google_maps_link": result.get("url"),
        "google_share_link": f"https://maps.google.com/?q=place_id:{place_id}",
        "google_review_link": f"https://search.google.com/local/reviews?placeid={place_id}",
    }

def query_grid_point(lat, lng, country):
    global api_request_count
    results = []
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": SEARCH_QUERY,
        "location": f"{lat},{lng}",
        "radius": RADIUS_METERS,
        "key": API_KEY
    }
    while True:
        response = requests.get(url, params=params).json()
        api_request_count += 1
        if response.get("status") != "OK":
            print(f"❌ API Error at ({lat}, {lng}): {response.get('status')}")
            break
        for place in response.get("results", []):
            place_id = place.get("place_id")
            if place_id and place_id not in seen_place_ids:
                seen_place_ids.add(place_id)
                details = fetch_place_details(place_id, lat, lng, country)
                if details:
                    results.append(details)
                    print(f"✅ Collected: {details['name']} at ({lat}, {lng})")
        if "next_page_token" in response:
            time.sleep(3)
            params = {"pagetoken": response["next_page_token"], "key": API_KEY}
        else:
            break
        if api_request_count >= API_QUOTA_LIMIT * WARNING_THRESHOLD:
            print("⚠️ Approaching API quota limit. Stopping.")
            return results
    return results

def save_to_csv(data):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"Raw data/consolidated_{timestamp}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in data:
            writer.writerow({key: row.get(key, "") for key in FIELDS})
    print(f"📁 Consolidated data saved to {filename}")
    return filename

def generate_interactive_map(data, output_html="Raw data/restaurants_map.html"):
    print("🗺️ Generating interactive map with clustering...")
    if not data:
        print("⚠️ No data to map.")
        return

    first = data[0]
    m = folium.Map(location=[first["latitude"], first["longitude"]], zoom_start=6)
    marker_cluster = MarkerCluster().add_to(m)

    for place in data:
        popup = f"""<strong>{place['name']}</strong><br>
        {place['address']}<br>
        <a href="{place['website'] or '#'}" target="_blank">Website</a> |
        <a href="{place['google_maps_link'] or '#'}" target="_blank">Maps</a>"""
        folium.Marker(
            location=[place["latitude"], place["longitude"]],
            popup=folium.Popup(popup, max_width=300),
            tooltip=place["name"]
        ).add_to(marker_cluster)

    m.save(output_html)
    print(f"🌐 Interactive map saved to: {output_html}")

# ------------------ MAIN EXECUTION ------------------
if __name__ == "__main__":
    for country in COUNTRIES:
        print(f"\n🌍 Starting scrape for Vietnamese restaurants in {country}...")
        try:
            bounds, country_shape = get_country_bounds_and_shape(country)
            min_lng, min_lat, max_lng, max_lat = bounds
            grid_points = generate_grid_within_country(min_lng, min_lat, max_lng, max_lat, GRID_STEP_KM, country_shape)
            print(f"📍 Generated {len(grid_points)} grid points within {country}.")

            for lat, lng in grid_points:
                results = query_grid_point(lat, lng, country)
                all_data.extend(results)
                if api_request_count >= API_QUOTA_LIMIT * WARNING_THRESHOLD:
                    break
        except Exception as e:
            print(f"❌ Error processing {country}: {e}")

    filename = save_to_csv(all_data)
    generate_interactive_map(all_data)

    print("\n📊 FINAL REPORT")
    print(f"API Requests Used: {api_request_count}")
    print(f"Restaurants Collected: {restaurant_collected_count}")
    print(f"Quota Usage: {int((api_request_count/API_QUOTA_LIMIT)*100)}%")

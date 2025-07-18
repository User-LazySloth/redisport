import json
import redis

def load_pois_from_json(filepath):
    with open(filepath, 'r', encoding = 'utf-8') as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        else:
            return [data]

def store_pois_in_redis(pois, redis_client):
    count = 0

    for poi in pois:
        node_id = poi.get("ID")
        if not node_id:
            print(f"Skipping POI with missing ID: {poi}")
            continue

        try:
            lat = float(poi.get("Latitude"))
            lon = float(poi.get("Longitude"))
        except (ValueError, TypeError):
            print(f"Skipping POI with invalid coordinates: {poi}")
            continue

        amenity = poi.get("Amenity", "")
        name = poi.get("Name", "")
        name_en = poi.get("Name:EN", "")

        # Add to Redis GEO index
        redis_client.geoadd('POIS', (lon, lat, str(node_id)))

        # Prepare Redis hash
        poi_metadata = {
            "ID": node_id,
            "Amenity": amenity
        }

        if name_en:
            poi_metadata["Name"] = name_en
        else:
            poi_metadata["Name"] = name

        redis_client.hset(f'poi:{node_id}', mapping=poi_metadata)
        count += 1

        if not count%1000:
            print(f"Stored {count} POIs in Redis...")
    print(f"Finished storing {count} POIs.")


if __name__ == "__main__":
    # Update the port to match the one on which the Redis server is currently running
    redis_client = redis.Redis(host='localhost', port=21081, db=0)

    json_file_path = "pois.json" 
    print("Loading POIs from JSON...")
    pois = load_pois_from_json(json_file_path)

    print("Storing POIs in Redis...")
    store_pois_in_redis(pois, redis_client)

    # Final count check
    pois_count = redis_client.zcard('POIS')
    print(f"Total POIs in Redis geospatial index: {pois_count}")

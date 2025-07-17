from flask import Flask, request, jsonify, render_template
import redis
import json

app = Flask(__name__)
# Update the port to match the one on which the Redis server is currently running
r = redis.Redis(host = 'localhost', port = 21081, decode_responses = True)

GEO_KEY = "POIS"
CACHE_TTL = 60
LOG_CHANNEL = "search_logs"
LEADERBOARD_KEY = "search:leaderboard"

# ---------------------- UTILITIES ---------------------- #
def log(message):
    print("[LOG]", message)
    r.publish(LOG_CHANNEL, message)

@app.route("/")
def home():
    return render_template("index.html")

# ---------------------- SEARCH POIS ---------------------- #
@app.route("/search")
def search():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
        radius = float(request.args.get("radius"))

        key = f"cache:search:{lat}:{lon}:{radius}"

        # Checking the Redis cache to see if the POI has already been asked in the past 60 seconds
        cached = r.get(key)
        if cached:
            log(f"[INFO] CACHE_HIT for key: {key}")
            r.zincrby(LEADERBOARD_KEY, 1, key)
            return jsonify(json.loads(cached))

        # Performing geospatial search using the GEOSEARCH command in case of a Cache Miss
        log(f"[INFO] CACHE_MISS for key: {key}")
        results = r.geosearch(
            name = GEO_KEY,
            longitude = lon,
            latitude = lat,
            radius = radius,
            unit = 'm',
            withcoord = True
        )

        # Constructing a response utilizing the hash metadata to return as the query's solution
        response = []
        for item in results:
            node_id = item[0]
            coords = item[1]
            meta = r.hgetall(f"poi:{node_id}")
            meta["Latitude"] = coords[1]
            meta["Longitude"] = coords[0]
            response.append(meta)

        # Caching and returning the result
        r.set(key, json.dumps(response), ex=CACHE_TTL)
        r.zincrby(LEADERBOARD_KEY, 1, key)

        return jsonify(response)

    except Exception as e:
        log(f"[ERROR] {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------- ADD NEW POI ---------------------- #
@app.route("/add_location", methods=["POST"])
def add_location():
    try:
        data = request.get_json()
        node_id = str(data["ID"])
        lat = float(data["Latitude"])
        lon = float(data["Longitude"])
        name = data.get("Name", "")
        amenity = data.get("Amenity", "")

        # Add to geospatial index
        r.geoadd(GEO_KEY, (lon, lat, node_id))

        # Store metadata as hash
        poi_metadata = {
            "ID": node_id,
            "Amenity": amenity,
            "Name": name
        }

        r.hset(f"poi:{node_id}", mapping = poi_metadata)

        log(f"[INFO] Added new POI {node_id} at ({lat}, {lon})")
        return jsonify({"status": "success", "message": "Location added."})

    except Exception as e:
        log(f"[ERROR] {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------- TOP SEARCHED AREAS ---------------------- #
@app.route("/top_queries")
def top_queries():
    top = r.zrevrange(LEADERBOARD_KEY, 0, 9, withscores=True)
    return jsonify([
        {"query": key, "count": int(score)} for key, score in top
    ])

# ---------------------- START APP ---------------------- #
if __name__ == "__main__":
    # Change the port to the port number on which you want to run the frontend
    app.run(host = '0.0.0.0', port = 21089, debug = True)

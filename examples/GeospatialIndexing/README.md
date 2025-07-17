# Geospatial Indexing using Redis

This is a full-stack web application built with Flask and Redis that allows users to manage and search for Points of Interest (POIs) based on their geospatial location. The application demonstrates how Redis can be used not just as a cache, but as a powerful backend for geospatial search, caching, metadata storage, and leaderboards.

## Features

- Geospatial Search: Find nearby POIs using latitude, longitude, and radius.
- Add New Locations: Add new POIs using a form-based interface.
- Performance Caching: Repeated queries are cached for fast results.
- Top Searches Leaderboard: Real-time tracking of most searched locations.


## Tech Stack

- Backend: Python (Flask)
- Frontend: HTML, CSS, JavaScript
- Database: Redis
- Python Packages: flask, redis

## How to Run the Project Locally

### Prerequisites

- Python 3.x
- pip
- Redis installed and running

### Step-by-Step Setup

1. Install all the dependencies if not present
    ```
    pip install flask redis json
    ```
2. CURL the datset from the previoulsy mentioned website as per your choice:
    ```
    curl -O https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf
    ```
3. Convert the POI data into the appropriate JSON form and then load it into redis by running the following command:
    ```
    python convert.py
    ``` 
4. Start the redis server:
    ```
    redis-server redis.conf
    ```
5. Simultaneouldy, run the application:
    ```
    python app.py
    ```
6. Access the application in your browser:
    ```
    Go to http://127.0.0.1:21089
    ```
* **Note**:</br>
In case you would like to load the POIs of another region, please visit this website: https://download.geofabrik.de/ to select the region of your choice and ensure to modify the CURL request at step 2 to look something like so:
    ```
    curl -O https://download.geofabrik.de/<SpecificDataset>>
    ```
    After doing this, please also ensure to modify the filepath present in convert.py to the appropriate dataset name

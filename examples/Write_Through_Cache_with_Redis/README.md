# Write-through cache using redis

- simple demo showing redis write-through caching with sqlite (can replace with DB of choice in config and corrsponding lib for demo)
- Intended to show usecase in places where data is distributed over a lot of machines, maybe sharded even and thus having a cache for better reads and also using it to batch write and pool them to the DB makes it faster and efficient especially in cases where consistency is important

## how to run

### terminal 1
```bash
# start redis server
redis-server redis.conf # configure port in redis.conf (for example 21083)
```

### terminal 2
```bash
# monitoring all GET, SET, GETEX, SETEX, LPUSH, etc. ops
redis-cli -p 21083 MONITOR
```

### terminal 3
```bash
python -m venv .venv # virtual env
source .venv/bin/activate
pip install -r requirements.txt


chmod +x run_demo.sh
./run_demo.sh
```

### Singular runs
```bash
# run full demo
python demo_application.py

# run quick version (smaller dataset)
python demo_application.py --quick

# run specific tests
python demo_application.py --writes-only
python demo_application.py --reads-only

# performance analysis
python performance_analyzer.py
```

## Demo modes

### In this demo, the reads are way faster and the writes would be a little slower on a truly distributed system as im assuming a sqlite instance on the same machine

### Write performance test
compares individual writes vs batch writes
- individual: writes one record at a time (slow)
- batch: writes multiple records together (fast)

### Read performance test
compares cache misses vs cache hits
- cold cache: reads from sqlite database (slow)
- warm cache: reads from redis cache (fast)

### Concurrent operations
simulates multiple users accessing the system at the same time (not true concurrency here as redis is single-threaded)

### performance analyzer
runs comprehensive benchmarks and generates detailed reports

## What the stats mean

### write stats
- **records/sec**: how many database writes per second
- **time**: total time for the operation
- **improvement %**: how much faster batch writes are vs individual

### read stats  
- **avg time (ms)**: average response time in milliseconds
- **cache hits**: reads served from redis cache
- **cache misses**: reads that had to go to sqlite
- **hit ratio**: percentage of reads served from cache
- **speedup**: how much faster cache reads are vs database reads

### cache stats
- **total reads/writes**: total operations performed
- **cache hits/misses**: breakdown of where data came from
- **hit ratio %**: cache effectiveness (higher is better)

## Requirements

- python 3.6+
- redis server
- sqlite3
- packages in requirements.txt 
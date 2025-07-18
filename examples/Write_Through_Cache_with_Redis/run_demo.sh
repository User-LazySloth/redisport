#!/bin/sh

# Set z/OS environment
echo "Setting up z/OS environment..."
export _BPXK_AUTOCVT=ON
export _CEE_RUNOPTS="FILETAG(AUTOCVT,AUTOTAG) POSIX(ON)"
export LC_ALL=C
export PYTHONIOENCODING=utf-8
export _TAG_REDIR_ERR=txt
export _TAG_REDIR_IN=txt
export _TAG_REDIR_OUT=txt
export PATH="/data/zopen/usr/local/bin:$PATH"
echo "Environment configured"

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    . venv/bin/activate
fi

# Check Redis connection
echo "Checking Redis connection..."
if python3 -c "
import redis
try:
    r = redis.Redis(host='localhost', port=21083, socket_connect_timeout=2)
    r.ping()
    print('Redis connection successful')
except Exception as e:
    print(f'Redis connection failed: {e}')
    exit(1)
" 2>/dev/null; then
    echo "Redis is ready on port 21083"
else
    echo "ERROR: Redis not available. Start Redis first:"
    echo "   redis-server --port 21083"
    exit 1
fi

# Check SQLite
echo "Checking SQLite..."
if /data/zopen/usr/local/bin/sqlite3 --version >/dev/null 2>&1; then
    SQLITE_VERSION=$(/data/zopen/usr/local/bin/sqlite3 --version | cut -d' ' -f1)
    echo "SQLite found: Version $SQLITE_VERSION"
else
    echo "ERROR: SQLite not found at /data/zopen/usr/local/bin/sqlite3"
    exit 1
fi

echo ""
echo "Starting Redis Write-Through Cache Demo"
echo ""
echo "IMPORTANT: To see Redis commands, run this in another terminal:"
echo "   redis-cli -p 21083 MONITOR"
echo ""
echo "Demo modes:"
echo "1) Quick demo"
echo "2) Full demo"
echo "3) Write performance only"
echo "4) Read performance only"
echo ""
printf "Enter choice [1-4]: "
read choice

case $choice in
    1)
        echo "Running quick demo..."
        python3 demo_application.py --quick
        ;;
    2)
        echo "Running full demo..."
        python3 demo_application.py
        ;;
    3)
        echo "Running write performance..."
        python3 demo_application.py --writes-only
        ;;
    4)
        echo "Running read performance..."
        python3 demo_application.py --reads-only
        ;;
    *)
        echo "Invalid choice, running quick demo..."
        python3 demo_application.py --quick
        ;;
esac

echo ""
echo "Demo completed!" 
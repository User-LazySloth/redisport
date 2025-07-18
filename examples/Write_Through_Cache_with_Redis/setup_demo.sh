#!/bin/sh

set -e

DEMO_DIR=$(pwd)
VENV_DIR="venv"
REQUIREMENTS_FILE="requirements.txt"

check_prerequisites() {
    echo "Checking prerequisites..."
    
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_VERSION=$(python3 --version)
        echo "Python3 found: $PYTHON_VERSION"
        PYTHON_CMD="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_VERSION=$(python --version)
        echo "Python found: $PYTHON_VERSION"
        PYTHON_CMD="python"
    else
        echo "ERROR: Python not found. Please install Python 3.6 or higher"
        return 1
    fi
    
    if $PYTHON_CMD -m pip --version >/dev/null 2>&1; then
        PIP_VERSION=$($PYTHON_CMD -m pip --version)
        echo "pip found: $PIP_VERSION"
    else
        echo "ERROR: pip not found. Please install pip"
        return 1
    fi
    
    if $PYTHON_CMD -m venv --help >/dev/null 2>&1; then
        echo "Python venv module available"
    else
        echo "WARNING: Python venv module not available"
    fi
    
    return 0
}

setup_zos_environment() {
    echo "Setting up z/OS environment..."
    
    export _BPXK_AUTOCVT=ON
    export _CEE_RUNOPTS="FILETAG(AUTOCVT,AUTOTAG) POSIX(ON)"
    export LC_ALL=C
    export PYTHONIOENCODING=utf-8
    export PATH="/data/zopen/usr/local/bin:$PATH"
    export _TAG_REDIR_ERR=txt
    export _TAG_REDIR_IN=txt
    export _TAG_REDIR_OUT=txt
    
    echo "z/OS environment configured"
}

check_sqlite() {
    echo "Checking SQLite installation..."
    
    if command -v sqlite3 >/dev/null 2>&1; then
        SQLITE_VERSION=$(sqlite3 -version | cut -d' ' -f1)
        echo "SQLite3 found: Version $SQLITE_VERSION"
        
        if $PYTHON_CMD -c "import sqlite3; print('Python SQLite3 version:', sqlite3.version)" 2>/dev/null; then
            echo "Python SQLite3 module working"
            return 0
        else
            echo "ERROR: Python SQLite3 module not working"
            return 1
        fi
    else
        echo "ERROR: SQLite3 not found"
        echo "Running SQLite installation helper..."
        chmod +x install_sqlite.sh
        ./install_sqlite.sh
        return 1
    fi
}

check_redis() {
    echo "Checking Redis connection..."
    
    if $PYTHON_CMD -c "
import redis
try:
    r = redis.Redis(host='localhost', port=21083, socket_connect_timeout=2)
    r.ping()
    print('Redis connection successful')
    info = r.info()
    print(f'Redis version: {info.get(\"redis_version\", \"unknown\")}')
    print(f'Connected to Redis on port 21083')
except Exception as e:
    print(f'Redis connection failed: {e}')
    exit(1)
" 2>/dev/null; then
        echo "Redis is running and accessible"
        return 0
    else
        echo "WARNING: Redis connection failed"
        echo "Redis Setup Instructions:"
        echo "  1. Install Redis for z/OS"
        echo "  2. Start Redis server on port 21083:"
        echo "     redis-server --port 21083"
        echo "  3. Demo expects connection: localhost:21083"
        echo ""
        echo "To continue without Redis, the demo will use SQLite-only mode"
        return 1
    fi
}

create_virtual_environment() {
    echo "Setting up Python virtual environment..."
    
    if [ -d "$VENV_DIR" ]; then
        echo "Virtual environment already exists, removing..."
        rm -rf "$VENV_DIR"
    fi
    
    if $PYTHON_CMD -m venv "$VENV_DIR" 2>/dev/null; then
        echo "Virtual environment created"
        
        . "$VENV_DIR/bin/activate"
        echo "Virtual environment activated"
        
        $PYTHON_CMD -m pip install --upgrade pip
        echo "pip upgraded"
        
        return 0
    else
        echo "WARNING: Failed to create virtual environment, continuing without it"
        return 1
    fi
}

install_dependencies() {
    echo "Installing Python dependencies..."
    
    if [ -f "$REQUIREMENTS_FILE" ]; then
        echo "Installing dependencies from $REQUIREMENTS_FILE..."
        
        while IFS= read -r requirement; do
            case "$requirement" in
                ''|'#'*) continue ;;
            esac
            
            echo "Installing: $requirement"
            if $PYTHON_CMD -m pip install "$requirement"; then
                echo "Installed: $requirement"
            else
                echo "WARNING: Failed to install: $requirement"
            fi
        done < "$REQUIREMENTS_FILE"
        
        echo "Dependency installation completed"
    else
        echo "ERROR: Requirements file not found: $REQUIREMENTS_FILE"
        return 1
    fi
}

test_demo_components() {
    echo "Testing demo components..."
    
    if $PYTHON_CMD -c "from cache_manager import WriteThoughCacheManager; print('Cache manager import successful')" 2>/dev/null; then
        echo "Cache manager module working"
    else
        echo "ERROR: Cache manager module failed"
        return 1
    fi
    
    if $PYTHON_CMD -c "from demo_application import CacheDemo; print('Demo application import successful')" 2>/dev/null; then
        echo "Demo application module working"
    else
        echo "ERROR: Demo application module failed"
        return 1
    fi
    
    if $PYTHON_CMD -c "from performance_analyzer import PerformanceAnalyzer; print('Performance analyzer import successful')" 2>/dev/null; then
        echo "Performance analyzer module working"
    else
        echo "WARNING: Performance analyzer module failed (optional)"
    fi
    
    return 0
}

create_demo_data() {
    echo "Creating demo database and sample data..."
    
    $PYTHON_CMD -c "
from cache_manager import WriteThoughCacheManager
import json
import random

cache = WriteThoughCacheManager()
try:
    cache.connect()
    
    # Create sample users
    sample_users = []
    for i in range(100):
        user = {
            'username': f'demo_user_{i:03d}',
            'email': f'user_{i:03d}@demo.com',
            'profile_data': json.dumps({
                'age': random.randint(18, 65),
                'city': random.choice(['New York', 'London', 'Tokyo', 'Paris'])
            })
        }
        sample_users.append(user)
    
    cache.batch_write('users', sample_users)
    
    # Create sample products
    sample_products = []
    categories = ['Electronics', 'Books', 'Clothing', 'Home']
    for i in range(50):
        product = {
            'name': f'Demo Product {i:03d}',
            'price': round(random.uniform(10.0, 500.0), 2),
            'category': random.choice(categories),
            'description': f'Demo product {i:03d} description',
            'stock_quantity': random.randint(0, 100)
        }
        sample_products.append(product)
    
    cache.batch_write('products', sample_products)
    
    print('Demo data created successfully')
    
finally:
    cache.close()
" || echo "WARNING: Demo data creation failed (demo will still work)"
}

main() {
    echo "Redis Write-Through Cache Demo Setup"
    echo "====================================="
    
    if ! check_prerequisites; then
        echo "Prerequisites check failed"
        exit 1
    fi
    
    setup_zos_environment
    
    check_sqlite || echo "SQLite issues detected but continuing..."
    
    check_redis || echo "Redis issues detected but continuing..."
    
    if create_virtual_environment; then
        echo "Virtual environment ready"
    fi
    
    if ! install_dependencies; then
        echo "Dependency installation failed"
        exit 1
    fi
    
    if ! test_demo_components; then
        echo "Demo component tests failed"
        exit 1
    fi
    
    create_demo_data
    
    echo ""
    echo "Setup completed successfully!"
    echo ""
    echo "To run the demo:"
    echo "  ./run_demo.sh"
    echo ""
    echo "To start Redis server (if not running):"
    echo "  redis-server --port 21083"
    echo ""
    echo "Make sure Redis is running before starting the demo!"
}

main "$@" 
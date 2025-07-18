#!/bin/sh

set -e

check_sqlite() {
    echo "Checking for SQLite installation..."
    
    # Check common SQLite locations
    SQLITE_LOCATIONS="/data/zopen/usr/local/bin/sqlite3 /usr/local/bin/sqlite3 /usr/bin/sqlite3 /bin/sqlite3"
    
    for location in $SQLITE_LOCATIONS; do
        if [ -x "$location" ]; then
            echo "SQLite found at: $location"
            VERSION=$($location --version | cut -d' ' -f1)
            echo "SQLite version: $VERSION"
            
            # Add to PATH if not already there
            if ! echo "$PATH" | grep -q "$(dirname $location)"; then
                export PATH="$(dirname $location):$PATH"
                echo "Added $(dirname $location) to PATH"
            fi
            
            return 0
        fi
    done
    
    echo "SQLite not found in common locations"
    return 1
}

install_instructions() {
    echo ""
    echo "SQLite Installation Instructions for z/OS:"
    echo "=========================================="
    echo ""
    echo "Option 1: Using z/Open Tools"
    echo "   1. Install z/Open Tools if not already installed"
    echo "   2. Run: zopen install sqlite"
    echo "   3. Add to PATH: export PATH=\"/data/zopen/usr/local/bin:\$PATH\""
    echo ""
    echo "Option 2: Manual Installation"
    echo "   1. Download SQLite source from https://www.sqlite.org/download.html"
    echo "   2. Extract and compile:"
    echo "      tar -xzf sqlite-autoconf-*.tar.gz"
    echo "      cd sqlite-autoconf-*"
    echo "      ./configure --prefix=/usr/local"
    echo "      make"
    echo "      make install"
    echo ""
    echo "Option 3: Use System Package Manager"
    echo "   Contact your system administrator for SQLite installation"
    echo ""
    echo "After installation, update your environment:"
    echo "   export PATH=\"/data/zopen/usr/local/bin:\$PATH\""
    echo ""
    echo "Environment file location options:"
    echo "   ~/.profile"
    echo "   ~/.bashrc" 
    echo "   ~/.zshrc"
    echo ""
}

test_sqlite() {
    echo "Testing SQLite installation..."
    
    if command -v sqlite3 >/dev/null 2>&1; then
        SQLITE_VERSION=$(sqlite3 --version | cut -d' ' -f1)
        echo "SQLite test successful: Version $SQLITE_VERSION"
        
        # Test database creation
        TEST_DB="/tmp/sqlite_test_$$.db"
        if sqlite3 "$TEST_DB" "CREATE TABLE test (id INTEGER); INSERT INTO test VALUES (1); SELECT * FROM test;" >/dev/null 2>&1; then
            echo "SQLite database operations working"
            rm -f "$TEST_DB"
            return 0
        else
            echo "ERROR: SQLite database operations failed"
            rm -f "$TEST_DB"
            return 1
        fi
    else
        echo "ERROR: sqlite3 command not found"
        return 1
    fi
}

setup_environment() {
    echo "Setting up environment for SQLite..."
    
    # Add common SQLite paths
    export PATH="/data/zopen/usr/local/bin:/usr/local/bin:$PATH"
    
    # z/OS specific environment
    export _BPXK_AUTOCVT=ON
    export _CEE_RUNOPTS="FILETAG(AUTOCVT,AUTOTAG) POSIX(ON)"
    export LC_ALL=C
    
    echo "Environment configured"
}

main() {
    echo "SQLite Installation Helper for z/OS"
    echo "==================================="
    
    setup_environment
    
    if check_sqlite; then
        echo "SQLite is already installed and accessible"
        
        if test_sqlite; then
            echo "SQLite installation verified successfully"
            echo ""
            echo "Your SQLite is ready for the Redis demo!"
        else
            echo "WARNING: SQLite found but not working properly"
            install_instructions
        fi
    else
        echo "SQLite not found on this system"
        install_instructions
        
        echo ""
        echo "After installing SQLite, run this script again to verify the installation"
        exit 1
    fi
}

main "$@" 
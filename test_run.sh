#!/bin/env bash
# ==============================================================================
#  Configuration
# ==============================================================================
cp ../redis_tls.conf ./
# The directory containing the test suites
TESTS_DIR="tests"

# The host and port for the test runner
HOST="127.0.0.1"
PORT="21092"
# Redis configuration file
REDIS_CONF="./redis_tls.conf"

# The path to the local redis-server executable
REDIS_SERVER_CMD="./src/redis-server"

# Maximum time in seconds a single test is allowed to run. 2 minute = 120 seconds.
TIMEOUT_SECONDS=120

# Setting the log file path
LOG_FILE="../test_run.log"

# List of top-level directories inside 'tests' to scan for .tcl files.
DIRECTORIES_TO_SCAN="unit unit/type unit/cluster integration"

# The PLAIN TEXT string to search for in the output to identify an exception.
EXCEPTION_MARKER="[exception]:"

# ==============================================================================
#  Prerequisite Checks
# ==============================================================================
# Check for the 'timeout' command
if ! command -v timeout &> /dev/null; then
    echo "Error: The 'timeout' command is not found. Please install it (it's part of 'coreutils')."
    exit 1
fi

# Check for the 'redis-server' command
if ! [ -x "$REDIS_SERVER_CMD" ]; then
    echo "Error: The '$REDIS_SERVER_CMD' command is not found or is not executable."
    echo "This script expects it to be in the 'src' subdirectory after compilation."
    exit 1
fi

# Check for the Redis configuration file
if [ ! -f "$REDIS_CONF" ]; then
    echo "Error: Redis configuration file '$REDIS_CONF' not found in the project root."
    exit 1
fi

# Check for this script and 'runtest' being in the same directory (project root).
RUNTEST_CMD="./runtest"
if [ ! -x "$RUNTEST_CMD" ]; then
    echo "Error: '$RUNTEST_CMD' command not found or is not executable."
    echo "Please ensure this script and 'runtest' are in the same project root directory."
    exit 1
fi

# Ensure the tests directory exists
if [ ! -d "$TESTS_DIR" ]; then
    echo "Error: The '$TESTS_DIR' directory was not found in the project root."
    exit 1
fi

# ==============================================================================
#  Check if TLS certificates already exist
# ==============================================================================
if [ -d "redis/tests/tls" ]; then
    echo "TLS certificates already exist at $TESTS_DIR/tests/tls. Skipping generation."
else
    # ==============================================================================
    #  Generate TLS certificates for tests
    # ==============================================================================
    echo "Generating TLS certificates using ./utils/gen-test-certs.sh"
    if ! bash ./utils/gen-test-certs.sh; then
        echo "Error: Failed to generate TLS certificates."
        exit 1
    fi

    # ==============================================================================
    #  Organize the generated certificate files
    # ==============================================================================
    echo "Cleaning up certificate directory structure..."
    # Copy TLS files to redis/
    if cp -r ./tests/tls/* ./; then
        :
    else
        echo "Error: Failed to organize the certificate files."
        exit 1
    fi
fi

# ==============================================================================
#  Main Script Logic
# ==============================================================================
REDIS_PID=0
function cleanup() {
    if [ "$REDIS_PID" -ne 0 ] && kill -0 "$REDIS_PID" 2>/dev/null; then
        echo ""
        echo "-------------------------------------------------------------"
        echo "Script interrupted. Shutting down active Redis server (PID: $REDIS_PID)..."
        kill -INT "$REDIS_PID"
        wait "$REDIS_PID" 2>/dev/null
        echo "Redis server stopped."
    fi
}
trap cleanup EXIT INT TERM

# Initialize or clear the single log file
echo "Initializing log file: $LOG_FILE"
> "$LOG_FILE"

# A flag to track if any test fails during the run. 0 = success, 1 = failure.
exception_found_flag=0

echo "Starting test run..."
echo "Host: $HOST, Port: $PORT, Timeout: ${TIMEOUT_SECONDS}s"
echo "A new Redis server will be started and stopped for each test."
echo "Full results for every test will be written to '$LOG_FILE'."
echo "-------------------------------------------------------------"

for dir in $DIRECTORIES_TO_SCAN; do
    TARGET_DIR="$TESTS_DIR/$dir"

    if [ ! -d "$TARGET_DIR" ]; then
        continue
    fi

    find "$TARGET_DIR" -maxdepth 1 -name "*.tcl" -type f | while IFS= read -r test_file_full_path; do
        
        runtest_arg_path="${test_file_full_path#"$TESTS_DIR"}"
        runtest_arg_path="${runtest_arg_path#/}"
        runtest_arg_path="${runtest_arg_path%.tcl}"

        echo "-------------------------------------------------------------"
        echo "Preparing for test: $runtest_arg_path"

        # Start Redis server for this specific test 
	echo "  -> Starting Redis server..."
        $REDIS_SERVER_CMD "$REDIS_CONF" &
        REDIS_PID=$!
        sleep 2

        # Check if the server started successfully
        if ! kill -0 "$REDIS_PID" 2>/dev/null; then
            echo "  -> FAILED TO START REDIS!"
            {
                echo "======================================================================="
                echo "SERVER STARTUP FAILED FOR: $test_file_full_path"
                echo "======================================================================="
                echo "[exception]: Could not start redis-server for this test."
                echo ""
                echo ""
            } >> "$LOG_FILE"
            exception_found_flag=1
            REDIS_PID=0
            continue
        fi
        
        echo -n "  -> Running test: $runtest_arg_path ... "
	echo "$PWD"
        output=$(timeout ${TIMEOUT_SECONDS}s "$RUNTEST_CMD" --host "$HOST" --port "$PORT" --tls --single "$runtest_arg_path" < /dev/null 2>&1)
        exit_code=$?

        # Stop Redis server after test execution 
	echo -n "Stopping Redis server ... "
        kill -INT "$REDIS_PID"
        wait "$REDIS_PID" 2>/dev/null
        REDIS_PID=0
        echo "Done."
	sleep 2

        if [ "$exit_code" -eq 124 ]; then
            echo "RESULT: TIMEOUT!"
            {
                echo "======================================================================="
                echo "TIMEOUT EXCEPTION IN: $test_file_full_path"
                echo "======================================================================="
                echo "[TIMEOUT]: Test was terminated after exceeding the ${TIMEOUT_SECONDS}-second limit."
                echo "--- Partial output captured before termination ---"
                echo "$output"
                echo ""
                echo ""
            } >> "$LOG_FILE"
            exception_found_flag=1
        elif echo "$output" | sed 's/\x1b\[[0-9;]*m//g' | grep -qF "$EXCEPTION_MARKER"; then
            echo "RESULT: EXCEPTION FOUND!"
            {
                echo "======================================================================="
                echo "EXCEPTION IN: $test_file_full_path"
                echo "======================================================================="
                echo "$output"
                echo ""
                echo ""
            } >> "$LOG_FILE"
            exception_found_flag=1
        else
            echo "RESULT: OK"
            {
                echo "======================================================================="
                echo "LOG FOR: $test_file_full_path"
                echo "======================================================================="
                echo "$output"
                echo ""
                echo ""
            } >> "$LOG_FILE"
        fi
    done
done

trap - EXIT

echo "-------------------------------------------------------------"
echo "Test run finished."

if [ "$exception_found_flag" -eq 1 ]; then
    echo "One or more exceptions or timeouts were found. Please review '$LOG_FILE' for complete details."
else
    echo "All tests completed without exceptions or timeouts. A complete record of the run is in '$LOG_FILE'."
fi

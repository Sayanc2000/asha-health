#!/bin/bash

# --- Configuration ---
BACKEND_DIR="backend"
FRONTEND_DIR="frontend"
DB_FILE="test.db" # Relative to BACKEND_DIR
DB_PATH="$BACKEND_DIR/$DB_FILE"
BACKEND_PID_FILE="backend.pid"
FRONTEND_PID_FILE="frontend.pid"
LOG_PREFIX="[run_app]"
BACKEND_PORT=8000

# --- Flags ---
FRESH_DB=false
SHOW_HELP=false

# --- Helper Functions ---
log() {
    echo "$LOG_PREFIX $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log "Error: Required command '$1' not found. Please install it."
        exit 1
    fi
}

cleanup() {
    log "Received interrupt signal. Shutting down servers..."
    if [ -f "$BACKEND_PID_FILE" ]; then
        BACKEND_PID=$(cat "$BACKEND_PID_FILE")
        log "Stopping backend server (PID: $BACKEND_PID)..."
        kill "$BACKEND_PID" &> /dev/null
        rm "$BACKEND_PID_FILE"
    fi
    if [ -f "$FRONTEND_PID_FILE" ]; then
        FRONTEND_PID=$(cat "$FRONTEND_PID_FILE")
        log "Stopping frontend server (PID: $FRONTEND_PID)..."
        kill "$FRONTEND_PID" &> /dev/null
        rm "$FRONTEND_PID_FILE"
    fi
    log "Cleanup complete."
    exit 0
}

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Run the application with both frontend and backend servers"
    echo ""
    echo "Options:"
    echo "  --fresh-db     Recreate the database from scratch"
    echo "  --help, -h     Display this help message and exit"
    echo ""
    echo "Examples:"
    echo "  $0                  Run the application with existing database"
    echo "  $0 --fresh-db       Run the application with a fresh database"
    exit 0
}

# --- Argument Parsing ---
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --fresh-db) FRESH_DB=true; log "Option --fresh-db enabled: Database will be recreated."; shift ;;
        --help|-h) SHOW_HELP=true; shift ;;
        *) log "Unknown parameter passed: $1"; echo "Use --help for usage information."; exit 1 ;;
    esac
    shift
done

# Show help if requested
if [ "$SHOW_HELP" = true ]; then
    show_help
fi

# --- Main Script ---

# Trap SIGINT (Ctrl+C) and SIGTERM
trap cleanup SIGINT SIGTERM

log "Starting application setup..."

# 1. Check if backend port is already in use
log "Checking if backend port $BACKEND_PORT is in use..."
EXISTING_PID=$(lsof -ti tcp:$BACKEND_PORT)

if [ -n "$EXISTING_PID" ]; then
    log "Port $BACKEND_PORT is already in use by PID $EXISTING_PID. Terminating process..."
    kill -9 $EXISTING_PID
    if [ $? -eq 0 ]; then
        log "Successfully terminated the process using port $BACKEND_PORT."
    else
        log "Error: Failed to terminate the process using port $BACKEND_PORT."
        exit 1
    fi
else
    log "Port $BACKEND_PORT is available."
fi

# 2. Check Dependencies
log "Checking dependencies..."
check_command "poetry"
check_command "node"
check_command "npm"
log "Dependencies check passed."

# 3. Handle Database
if [ "$FRESH_DB" = true ]; then
    log "Handling fresh database request..."
    if [ -f "$DB_PATH" ]; then
        log "Removing existing database file: $DB_PATH"
        rm "$DB_PATH"
        if [ $? -ne 0 ]; then
            log "Error: Failed to remove database file $DB_PATH"
            exit 1
        fi
    else
        log "No existing database file found at $DB_PATH."
    fi
    log "Database will be migrated automatically when the server starts."
else
    log "Persisting existing database (if any)."
fi

# 4. Install Dependencies
log "Installing backend dependencies..."
(cd "$BACKEND_DIR" && poetry install)
if [ $? -ne 0 ]; then
    log "Error: Failed to install backend dependencies."
    exit 1
fi
log "Backend dependencies installed."

log "Installing frontend dependencies..."
(cd "$FRONTEND_DIR" && npm install)
if [ $? -ne 0 ]; then
    log "Error: Failed to install frontend dependencies."
    exit 1
fi
log "Frontend dependencies installed."

# 5. Start Servers (migrations will happen automatically if fresh DB)
log "Starting backend server..."
(cd "$BACKEND_DIR" && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT) &
BACKEND_PID=$!
echo $BACKEND_PID > "$BACKEND_PID_FILE"
log "Backend server started (PID: $BACKEND_PID)."

log "Starting frontend server..."
(cd "$FRONTEND_DIR" && npm run dev) &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$FRONTEND_PID_FILE"
log "Frontend server started (PID: $FRONTEND_PID)."

# Wait for servers to exit (they won't until interrupted)
log "Application is running. Press Ctrl+C to stop."
wait

#!/bin/bash
# Script to run the WebSocket transcription test
# This script starts the FastAPI server, waits for it to initialize,
# then runs the WebSocket test script.

echo "=== Starting Asha Transcription API Server ==="
# Start the server in the background
poetry run uvicorn app.main:app --reload > server.log 2>&1 &
SERVER_PID=$!

# Wait for the server to initialize (5 seconds)
echo "Waiting for server to start..."
sleep 5

# Check if the server is running
if kill -0 $SERVER_PID 2>/dev/null; then
    echo "Server started successfully (PID: $SERVER_PID)"
    
    echo -e "\n=== Running WebSocket Transcription Test ==="
    # Run the WebSocket test
    poetry run python -m tests.test_websocket_transcription
    
    # Capture the test result
    TEST_RESULT=$?
    
    echo -e "\n=== Shutting down server ==="
    # Kill the server
    kill $SERVER_PID
    wait $SERVER_PID 2>/dev/null
    
    # Return the test result
    exit $TEST_RESULT
else
    echo "Failed to start the server. Check server.log for details."
    exit 1
fi 
# Asha Transcription API Tests

This directory contains test scripts for the Asha Transcription API.

## Available Tests

- **`test_store.py`**: Tests for the in-memory transcript store and dispatcher
- **`test_client.py`**: Tests for the WebSocket client functionality
- **`test_api_endpoint.py`**: Tests for the REST API transcription endpoint
- **`chunk_and_test.py`**: Tests for audio chunking and transcription
- **`run_all_tests.py`**: Runner script that executes all tests sequentially
- **`test_websocket_transcription.py`**: End-to-end WebSocket transcription test

## End-to-End WebSocket Transcription Test

The `test_websocket_transcription.py` script tests the full transcription pipeline:

1. Loads an audio file (`aws-bp-30 (1).mp3`)
2. Splits it into 5-second chunks (up to 1 minute of audio)
3. Sends each chunk to the WebSocket endpoint
4. Verifies that transcripts are stored in the database

This test is ideal for validating that the transcription service, in-memory storage, and database dispatcher are all working together correctly.

### Running the Test

#### Option 1: Using the Convenience Script

The easiest way to run the test is using the provided shell script:

```bash
cd backend
./run_websocket_test.sh
```

This script will:

1. Start the FastAPI server
2. Run the WebSocket test
3. Shut down the server when the test completes

#### Option 2: Manual Setup

If you prefer to run the components separately:

1. Start the server in one terminal:

   ```bash
   cd backend
   poetry run uvicorn app.main:app --reload
   ```

2. Run the test in another terminal:
   ```bash
   cd backend
   poetry run python -m tests.test_websocket_transcription
   ```

### Test Output

The test will:

- Log detailed information to `websocket_test.log`
- Display summary information in the console
- Verify if all transcripts were saved to the database

### Test Parameters

You can modify these parameters in `test_websocket_transcription.py`:

- `CHUNK_LENGTH_MS`: Length of each audio chunk (default: 5000ms = 5 seconds)
- `MAX_DURATION_MS`: Maximum audio duration to process (default: 60000ms = 1 minute)
- `WEBSOCKET_URL`: WebSocket endpoint URL (default: "ws://localhost:8000/ws/")

## Other Tests

To run other tests:

```bash
# Run all tests
poetry run python -m tests.run_all_tests

# Run specific tests
poetry run python -m tests.test_store
poetry run python -m tests.test_client
poetry run python -m tests.test_api_endpoint
poetry run python -m tests.chunk_and_test
```

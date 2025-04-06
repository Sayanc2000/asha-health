# Asha Transcription Service

A WebSocket-based service for real-time audio transcription using FastAPI and asyncio.

## Features

- WebSocket endpoint for receiving 5-second audio chunks with serial numbers
- Factory pattern for easily swappable transcription services:
  - Dummy service for testing
  - Deepgram API integration
  - OpenAI Whisper API integration
- Asynchronous processing of audio transcription
- In-memory interim transcript storage
- RESTful API endpoints for managing transcriptions
- Configuration via environment variables
- Database models for future persistence

## Requirements

- Python 3.12+
- Poetry for dependency management

## Installation

1. Ensure you have Python 3.12+ and Poetry installed
2. Clone the repository
3. Install dependencies:

```bash
cd backend
poetry install
```

4. Copy the example environment file and configure as needed:

```bash
cp .env.example .env
```

## Configuration

The application is configured using environment variables or a `.env` file. Available settings include:

- `DATABASE_URL`: Database connection string (default: `sqlite+aiosqlite:///./test.db`)
- `TRANSCRIPTION_PROVIDER`: Transcription service provider (options: `dummy`, `deepgram`, `whisper`, default: `dummy`)
- `DEEPGRAM_API_KEY`: API key for Deepgram transcription service
- `OPENAI_API_KEY`: API key for OpenAI Whisper transcription service
- `LOG_LEVEL`: Logging level (default: `INFO`)
- `LOG_FILE`: Log file path (default: `app.log`)
- `LOG_ROTATION`: Log file rotation size (default: `500 MB`)

## Running the Application

Start the application using:

```bash
cd backend
poetry run uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000.

- API documentation: http://localhost:8000/docs
- WebSocket endpoint: `ws://localhost:8000/ws/{session_id}`
- RESTful API:
  - `GET /api/sessions`: List all active transcription sessions
  - `GET /api/sessions/{session_id}`: Get all transcripts for a specific session
  - `POST /api/transcribe`: Transcribe audio using the configured provider

## Running Tests

The project includes several test scripts in the `tests` directory:

```bash
cd backend

# Run all tests
poetry run python -m tests.run_all_tests

# Run specific tests
poetry run python -m tests.test_store
poetry run python -m tests.test_client
poetry run python -m tests.test_api_endpoint
poetry run python -m tests.chunk_and_test
```

### Available Tests

- `test_store.py`: Tests for the in-memory transcript store and dispatcher
- `test_client.py`: Tests for the WebSocket client functionality
- `test_api_endpoint.py`: Tests for the REST API transcription endpoint
- `chunk_and_test.py`: Tests for audio chunking and transcription
- `run_all_tests.py`: Runner script that executes all tests sequentially

Note: Some tests require the API server to be running, and others require valid API keys for transcription services.

### End-to-End WebSocket Transcription Test

A comprehensive end-to-end test is available that tests the full transcription pipeline:

```bash
# Easy way to run the WebSocket test (starts and stops the server automatically)
./run_websocket_test.sh

# Or run the test manually after starting the server
poetry run python -m tests.test_websocket_transcription
```

This test:

1. Loads an audio file (aws-bp-30 (1).mp3)
2. Splits it into 5-second chunks (up to 1 minute of audio)
3. Sends each chunk to the WebSocket endpoint
4. Verifies that transcripts are stored in the database

For more details, see `tests/README.md`.

## WebSocket Usage

Connect to the WebSocket endpoint with a session ID and send JSON messages with the following format:

```json
{
  "serial": 1,
  "audio_data": "base64_encoded_audio_data",
  "provider": "deepgram" // Optional, uses default if not specified
}
```

The server will respond with:

```json
{
  "status": "success",
  "serial": 1,
  "transcript": "Transcribed text from the audio chunk"
}
```

## REST API Usage

### Transcribe Audio

```bash
curl -X POST "http://localhost:8000/api/transcribe" \
  -H "Content-Type: application/json" \
  -d '{"audio_data": "base64_encoded_audio_data", "provider": "whisper"}'
```

### List All Sessions

```bash
curl -X GET "http://localhost:8000/api/sessions"
```

### Get Session Transcripts

```bash
curl -X GET "http://localhost:8000/api/sessions/your-session-id"
```

## Adding New Transcription Services

The system uses a factory pattern to make adding new transcription services easy:

1. Create a new class that inherits from `BaseTranscriptionService`
2. Implement the `async def transcribe(self, audio_data: str) -> str` method
3. Update the factory in `app/transcription/factory.py` to include your new service

## Architecture

The application uses:

- FastAPI for the REST API and WebSocket endpoints
- Async SQLAlchemy for database operations
- Factory pattern for transcription services
- Dependency injection for configuration
- Pydantic for data validation and settings management

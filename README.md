# Asha Clinic Transcription Service

A real-time doctor-patient encounter transcription system that generates SOAP note summaries.

## Quick Start

1. Install prerequisites:
   - Python 3.12+
   - Node.js (v18+ recommended)
   - Poetry (Python dependency management)
   - npm (Node package manager)

2. Clone the repository
3. Configure environment variables:
Makre sure you are in backend folder otherwise run the cd command
```bash
cd backend
cp .env.example .env
# Edit .env with your API keys
```
4. Run the application:
Make sure you are in root folder
```bash
chmod +x run_app.sh
./run_app.sh
```

### Optional Flags

- `--fresh-db`: Start with a clean database
- `--help`: Show usage information

Example:
```bash
./run_app.sh --fresh-db
```

## Features

- **Near Real-time Transcription**:
  - WebSocket-based audio streaming
  - Multiple transcription providers (Deepgram, Whisper)
  
- **SOAP Note Generation**:
  - Automatic summarization of transcripts
  - Structured SOAP format (Subjective, Objective, Assessment, Plan)
  - Real-time status notifications

- **Notification System**:
  - Server-Sent Events (SSE) for updates
  - Processing status updates
  - Error notifications

- **Modular Architecture**:
  - Factory pattern for services for easy decoupling if required

## Detailed Setup

### Backend

1. Install Python dependencies:
```bash
cd backend
poetry install
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. Run backend:
```bash
poetry run uvicorn app.main:app --reload
```

### Frontend

1. Install Node.js dependencies:
```bash
cd frontend
npm install
```

2. Run frontend:
```bash
npm run dev
```

## Architecture

### Backend Components

- **WebSocket Server**: Handles real-time audio streaming
- **Transcription Services**: Factory pattern for multiple providers
- **Notification System**: SSE for real-time updates
- **SOAP Processor**: Generates medical notes from transcripts
- **Database**: SQLite for session storage

### Frontend Components

- **WebSocket Client**: Connects to backend
- **Audio Capture**: Handles microphone input
- **Notification Handler**: Processes SSE updates
- **UI**: Displays transcripts and SOAP notes

## Configuration

### Backend Environment Variables

- `DATABASE_URL`: Database connection string
- `TRANSCRIPTION_PROVIDER`: `deepgram`
- `DEEPGRAM_API_KEY`: API key for Deepgram
- `OPENAI_API_KEY`: API key for Whisper Optional


### Frontend Configuration

Configured in `frontend/next.config.js`:
- Backend API URL
- WebSocket endpoint
- Notification endpoint

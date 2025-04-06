# Asha Transcription Frontend

This is a Next.js application that connects to the Asha Transcription API to test WebSocket-based audio transcription.

## Getting Started

1. Install dependencies:

```bash
npm install
```

2. Start the development server:

```bash
npm run dev
```

3. Open [http://localhost:3000](http://localhost:3000) in your browser to see the application.

## Features

- Connect to the WebSocket server
- Send test audio file
- Display transcription results in real time

## Usage

1. Click "Connect WebSocket" to establish a connection with the backend
2. Click "Send Test Audio" to send the sample audio for transcription
3. View the transcription results in the transcript box

## Requirements

- The backend server should be running on port 8000
- The sample audio file (audio_chunk_10s.wav) should be available in the backend directory

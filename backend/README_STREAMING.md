# Streaming Transcription Feature

This document explains how to use the real-time streaming transcription with diarization feature in the Asha Transcription API.

## Overview

The streaming transcription feature allows for real-time audio transcription with speaker diarization capabilities. This enables:

- Lower latency transcription results during ongoing speech
- Real-time speaker identification (diarization)
- Continuous text updates as people speak
- Automatic segmentation into utterances by speaker

## Configuration

To enable streaming transcription:

1. Set the following environment variables in your `.env` file:

   ```
   TRANSCRIPTION_PROVIDER=deepgram
   USE_STREAMING_TRANSCRIPTION=true
   DEEPGRAM_API_KEY=your_api_key_here
   ```

2. Restart the server:
   ```
   poetry run uvicorn app.main:app --reload
   ```

## How It Works

The streaming transcription uses Deepgram's WebSocket API to provide real-time transcription:

1. The client connects to the WebSocket endpoint `/ws/{session_id}` (same as non-streaming mode)
2. The server establishes a connection to Deepgram on behalf of the client
3. Audio chunks are forwarded from client → server → Deepgram
4. Transcription results are sent from Deepgram → server → client
5. Final results are automatically stored in the database

## WebSocket Protocol

### Connection Flow

1. Client connects to `/ws/{session_id}`
2. Server responds with connection acknowledgment:
   ```json
   {
     "status": "connected",
     "message": "Connected to streaming transcription service",
     "streaming": true
   }
   ```

### Sending Audio

Send audio data as binary WebSocket messages (preferred):

```javascript
// JavaScript example
const audioChunk = new Uint8Array(/* your audio data */);
websocket.send(audioChunk);
```

Alternatively, you can send base64-encoded audio in JSON:

```javascript
// JavaScript example
const base64Audio = btoa(
  String.fromCharCode.apply(null, new Uint8Array(/* your audio data */))
);
websocket.send(
  JSON.stringify({
    audio_data: base64Audio,
  })
);
```

### Receiving Transcription Results

The server sends transcript updates in this format:

```json
{
  "status": "transcript_update",
  "session_id": "your-session-id",
  "data": {
    "text": "The complete transcribed text.",
    "segments": [
      {
        "id": 0,
        "start": 0.0,
        "end": 2.5,
        "text": "The first segment",
        "speaker": "SPEAKER_00"
      },
      {
        "id": 1,
        "start": 2.5,
        "end": 5.0,
        "text": "The second segment from another speaker.",
        "speaker": "SPEAKER_01"
      }
    ],
    "speakers": ["SPEAKER_00", "SPEAKER_01"],
    "is_final": false
  },
  "is_final": false,
  "serial": null
}
```

- When `is_final` is `false`, the transcript is an interim result that might change
- When `is_final` is `true`, the transcript is a final result and includes a `serial` number

## Audio Format Requirements

For optimal results:

- Sample rate: 16 kHz
- Channels: Mono
- Encoding: 16-bit PCM (linear16)
- Chunk size: ~100-200ms of audio per message (recommended)

## Testing the Streaming Feature

A test script is included to demo the streaming feature:

```bash
# Create a session first
curl -X POST http://localhost:8000/api/sessions -H "Content-Type: application/json" -d '{"name":"Test Session"}'
# Note the session ID from the response

# Run the test script with an audio file
python test_stream.py your-session-id path/to/audio.wav
```

Make sure your audio file is in the required format (16 kHz mono PCM) for best results.

## Limitations and Considerations

- Streaming requires a stable internet connection
- Audio must be high quality for best transcription results
- The current implementation is optimized for English language
- If streaming fails, the system will automatically fall back to batch mode
- Each session requires additional server resources, so there's a practical limit to concurrent sessions

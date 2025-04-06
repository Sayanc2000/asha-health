# Server-Sent Events (SSE) Notification System

This module implements a real-time notification system using Server-Sent Events (SSE) for Asha's backend. It enables delivering asynchronous updates to connected clients, particularly for long-running operations like SOAP note generation.

## Architecture

- `SSEManager`: Singleton class managing client connections and message queues
- `Notification Service`: Formats and sends typed notifications to specific clients
- `SSE Endpoint`: FastAPI route for clients to establish SSE connections

## Current Implementation

The current implementation supports SOAP note processing notifications with the following statuses:

- `processing`: The SOAP note generation has started
- `completed`: The SOAP note was successfully generated
- `failed`: The SOAP note generation failed (includes error message)

## Example Message Format

```json
{
  "type": "soap_update",
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "message": "SOAP note generated successfully."
}
```

## Client-Side Implementation (Frontend)

To connect to the SSE endpoint from the frontend:

```javascript
const sessionId = "your-session-id";
const eventSource = new EventSource(`/notifications/sse/${sessionId}`);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);

  // Handle different notification types
  if (data.type === "soap_update") {
    switch (data.status) {
      case "processing":
        console.log("SOAP generation started:", data.message);
        // Show loading indicator
        break;
      case "completed":
        console.log("SOAP generation completed:", data.message);
        // Update UI, maybe fetch the SOAP note
        break;
      case "failed":
        console.error("SOAP generation failed:", data.message);
        // Show error message
        break;
    }
  }
};

// Handle connection errors
eventSource.onerror = (error) => {
  console.error("SSE connection error:", error);
  eventSource.close();
};

// Close connection when no longer needed
function closeConnection() {
  eventSource.close();
}
```

## Extending with New Notification Types

To add a new notification type, add a new function in `notification/service.py` following the pattern of `send_soap_notification()`.

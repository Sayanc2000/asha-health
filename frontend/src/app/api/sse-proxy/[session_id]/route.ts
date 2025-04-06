import { NextRequest } from 'next/server';

// Ensure this matches your backend address
const BACKEND_SSE_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export const dynamic = 'force-dynamic'; // Ensure this route is not statically generated

export async function GET(
  request: NextRequest,
  { params }: { params: { session_id: string } }
) {
  const sessionId = params.session_id;

  if (!sessionId) {
    return new Response('Missing session_id', { status: 400 });
  }

  console.log(`SSE Proxy: Attempting connection for session ${sessionId}`);

  try {
    const backendUrl = `${BACKEND_SSE_URL}/notifications/sse/${sessionId}`;
    const response = await fetch(backendUrl, {
      headers: {
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        // Forward any necessary headers from the original request if needed
        // 'Authorization': request.headers.get('Authorization') || '',
      },
      // IMPORTANT: Duplex required for streaming responses in Next.js Route Handlers
      // @ts-ignore - Property 'duplex' does not exist on type 'RequestInit'. This is required for streaming.
      duplex: 'half'
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`SSE Proxy: Backend connection failed for ${sessionId}: ${response.status} ${errorText}`);
      return new Response(errorText || 'Failed to connect to backend SSE', { status: response.status });
    }

    // Ensure the response body is a ReadableStream
    if (!response.body) {
      console.error(`SSE Proxy: Backend response body is null for ${sessionId}`);
      return new Response('Backend response body is null', { status: 500 });
    }

    console.log(`SSE Proxy: Connection established for session ${sessionId}. Streaming...`);

    // Stream the response back to the client
    return new Response(response.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no', // Important for Nginx environments
      },
    });

  } catch (error: any) {
    console.error(`SSE Proxy: Error connecting to backend for ${sessionId}:`, error);
    return new Response(`Internal Server Error: ${error.message}`, { status: 500 });
  }
} 
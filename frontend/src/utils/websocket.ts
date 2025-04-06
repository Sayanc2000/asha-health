type TranscriptionMessage = {
  status: string;
  serial: number;
  transcript: string;
  message?: string;
};

type MessageCallback = (message: TranscriptionMessage) => void;
type ErrorCallback = (error: string, event?: Event) => void;
type CloseCallback = (event: CloseEvent) => void;

/**
 * Helper to extract meaningful error information from WebSocket events
 */
const formatWebSocketError = (event: Event): string => {
  if (!event) return 'Unknown error';
  
  // Try to extract more information from the event
  const wsEvent = event as any;
  
  if (wsEvent.message) return wsEvent.message;
  if (wsEvent.reason) return wsEvent.reason;
  if (wsEvent.type) return `WebSocket ${wsEvent.type} error`;
  
  // For connection errors, provide more specific information
  if (wsEvent.target && wsEvent.target.url) {
    return `Connection failed to ${wsEvent.target.url}`;
  }
  
  return 'WebSocket connection failed';
};

export class TranscriptionWebSocket {
  private socket: WebSocket | null = null;
  private sessionId: string;
  private serverUrl: string;
  private counter: number = 0;
  
  constructor(serverUrl: string = 'ws://localhost:8000', sessionId?: string) {
    this.sessionId = sessionId || this.generateSessionId();
    this.serverUrl = serverUrl;
  }
  
  private generateSessionId(): string {
    return 'session-' + Math.random().toString(36).substring(2, 15);
  }
  
  connect(
    onMessage: MessageCallback,
    onError?: ErrorCallback,
    onClose?: CloseCallback
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        const fullUrl = `${this.serverUrl}/ws/${this.sessionId}`;
        console.log(`Attempting to connect to WebSocket at: ${fullUrl}`);
        
        // Reset any existing socket
        if (this.socket) {
          console.log('Closing existing WebSocket connection before creating a new one');
          this.close();
        }
        
        this.socket = new WebSocket(fullUrl);
        console.log(`WebSocket created with readyState: ${this.getReadyStateDescription()}`);
        
        // Define onopen first to avoid race conditions with timeout
        this.socket.onopen = () => {
          console.log('WebSocket connection established successfully');
          // Clear any pending timeout
          if (connectionTimeout) {
            clearTimeout(connectionTimeout);
          }
          resolve();
        };
        
        this.socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data);
            onMessage(data);
          } catch (parseError) {
            console.error('Failed to parse WebSocket message:', parseError, 'Raw data:', event.data);
            if (onError) onError(`Failed to parse server message: ${parseError}`);
          }
        };
        
        this.socket.onerror = (event) => {
          const errorMessage = formatWebSocketError(event);
          console.error(`WebSocket error: ${errorMessage}`, event);
          
          if (onError) onError(errorMessage, event);
          reject(new Error(errorMessage));
        };
        
        this.socket.onclose = (event) => {
          const reason = event.reason || (event.wasClean ? 'Connection closed cleanly' : 'Connection closed unexpectedly');
          console.log(`WebSocket connection closed: ${reason} (Code: ${event.code})`);
          
          if (onClose) onClose(event);
          
          // If connection was never established (closed before onopen)
          if (this.socket && this.socket.readyState !== WebSocket.OPEN) {
            reject(new Error(`WebSocket connection failed to establish: ${reason} (Code: ${event.code})`));
          }
        };
        
        // Set a connection timeout
        const connectionTimeout = setTimeout(() => {
          if (this.socket && this.socket.readyState !== WebSocket.OPEN) {
            const timeoutError = 'WebSocket connection timed out after 10 seconds';
            console.error(timeoutError);
            reject(new Error(timeoutError));
            
            // Clean up the socket
            this.close();
          }
        }, 10000);
        
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.error(`Failed to establish WebSocket connection: ${errorMessage}`, error);
        reject(new Error(`WebSocket initialization error: ${errorMessage}`));
      }
    });
  }
  
  /**
   * Send an audio chunk through the WebSocket
   */
  sendAudioChunk(audioData: string, provider?: string): void {
    if (!this.socket) {
      throw new Error('WebSocket not initialized');
    }
    
    // Check various states to provide clear error messages
    switch (this.socket.readyState) {
      case WebSocket.CONNECTING:
        throw new Error('WebSocket is still connecting, cannot send data yet');
      
      case WebSocket.CLOSING:
      case WebSocket.CLOSED:
        throw new Error(`WebSocket is ${this.getReadyStateDescription()}, cannot send data`);
        
      case WebSocket.OPEN:
        // This is the only state where we can proceed
        break;
        
      default:
        throw new Error(`WebSocket in unknown state (${this.socket.readyState}), cannot send data`);
    }
    
    const message = {
      serial: this.counter++,
      audio_data: audioData,
      ...(provider && { provider }),
    };
    
    try {
      this.socket.send(JSON.stringify(message));
    } catch (error) {
      console.error('Failed to send audio chunk:', error);
      
      // Extra logging to help diagnose issues
      console.error(`WebSocket state at time of send error: ${this.getReadyStateDescription()}`);
      
      throw error;
    }
  }
  
  /**
   * Safely close the WebSocket connection
   */
  close(): void {
    if (this.socket) {
      try {
        console.log('Closing WebSocket connection...');
        // Only attempt to close if not already closed
        if (this.socket.readyState !== WebSocket.CLOSED) {
          this.socket.close(1000, "Normal closure"); // 1000 is the "normal closure" code
        }
      } catch (error) {
        console.error('Error closing WebSocket:', error);
      } finally {
        this.socket = null;
      }
    }
  }
  
  /**
   * Gets a human-readable description of the current WebSocket state
   */
  private getReadyStateDescription(): string {
    if (!this.socket) return 'Not initialized';
    
    switch (this.socket.readyState) {
      case WebSocket.CONNECTING: return 'Connecting';
      case WebSocket.OPEN: return 'Open';
      case WebSocket.CLOSING: return 'Closing';
      case WebSocket.CLOSED: return 'Closed';
      default: return `Unknown (${this.socket.readyState})`;
    }
  }
  
  get isConnected(): boolean {
    return this.socket !== null && this.socket.readyState === WebSocket.OPEN;
  }
  
  get currentSessionId(): string {
    return this.sessionId;
  }
  
  get connectionStatus(): string {
    return this.getReadyStateDescription();
  }
} 
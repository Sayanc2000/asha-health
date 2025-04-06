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
  
  constructor(serverUrl: string = 'ws://localhost:8000') {
    this.sessionId = this.generateSessionId();
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
        
        this.socket = new WebSocket(fullUrl);
        
        this.socket.onopen = () => {
          console.log('WebSocket connection established successfully');
          resolve();
        };
        
        this.socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
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
            
            this.socket.close();
          }
        }, 10000);
        
        // Clear the timeout once connected
        this.socket.onopen = () => {
          clearTimeout(connectionTimeout);
          console.log('WebSocket connection established successfully');
          resolve();
        };
        
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.error(`Failed to establish WebSocket connection: ${errorMessage}`, error);
        reject(new Error(`WebSocket initialization error: ${errorMessage}`));
      }
    });
  }
  
  sendAudioChunk(audioData: string, provider?: string): void {
    if (!this.socket) {
      throw new Error('WebSocket not initialized');
    }
    
    if (this.socket.readyState !== WebSocket.OPEN) {
      throw new Error(`WebSocket not connected (state: ${this.getReadyStateDescription()})`);
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
      throw error;
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
  
  close(): void {
    if (this.socket) {
      console.log('Closing WebSocket connection...');
      this.socket.close();
      this.socket = null;
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
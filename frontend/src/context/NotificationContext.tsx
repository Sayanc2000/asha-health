'use client'; // This context provider will be used in client components

import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';

interface NotificationMessage {
  type: string; // e.g., "soap_update"
  session_id: string;
  status: 'processing' | 'completed' | 'failed';
  message: string;
  // Add other potential fields if needed
}

interface NotificationContextType {
  lastMessage: NotificationMessage | null;
  isConnected: boolean;
  error: string | null;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

interface NotificationProviderProps {
  sessionId: string | null; // Pass the session ID to connect for
  children: ReactNode;
}

export const NotificationProvider: React.FC<NotificationProviderProps> = ({ sessionId, children }) => {
  const [lastMessage, setLastMessage] = useState<NotificationMessage | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let eventSource: EventSource | null = null;

    if (sessionId) {
      console.log(`NotificationContext: Attempting SSE connection for session ${sessionId}`);
      const url = `/api/sse-proxy/${sessionId}`;
      
      try {
        eventSource = new EventSource(url);
        
        // Set a connection timeout - if we don't get a message in 5 seconds, 
        // consider it not connected
        const connectionTimeout = setTimeout(() => {
          if (!isConnected) {
            console.log(`NotificationContext: Connection timeout for ${sessionId}`);
            setError('Connection timeout');
          }
        }, 5000);
        
        // EventSource doesn't have a standard onopen handler that works consistently across browsers
        // We'll consider it connected as soon as we receive any message
        
        eventSource.onmessage = (event) => {
          // If this is the first message, set connected state
          if (!isConnected) {
            console.log(`NotificationContext: Connection established for ${sessionId}`);
            setIsConnected(true);
            setError(null);
          }
          
          try {
            const parsedData: NotificationMessage = JSON.parse(event.data);
            console.log(`NotificationContext: Received message for ${sessionId}:`, parsedData);
            
            // If this is a heartbeat message, we know the connection is active
            if (parsedData.type === 'heartbeat' && parsedData.status === 'connected') {
              console.log(`NotificationContext: Received heartbeat for ${sessionId}`);
              setIsConnected(true);
              setError(null);
              // Don't update lastMessage for heartbeats
            } else {
              // For other message types, update lastMessage state
              setLastMessage(parsedData);
            }
          } catch (e) {
            console.error('NotificationContext: Failed to parse SSE message data:', event.data, e);
            setError('Failed to parse message');
          }
        };
        
        eventSource.onerror = (err) => {
          console.error(`NotificationContext: SSE connection error for ${sessionId}:`, err);
          setIsConnected(false);
          setError('Connection error');
          clearTimeout(connectionTimeout);
          
          // Only close the connection if we're not in a reconnecting state
          if (eventSource && eventSource.readyState === EventSource.CLOSED) {
            eventSource.close();
          }
        };
        
        // Clean up the timeout when component unmounts or on successful connection
        return () => {
          clearTimeout(connectionTimeout);
          if (eventSource) {
            console.log(`NotificationContext: Closing SSE connection for session ${sessionId}`);
            eventSource.close();
            setIsConnected(false);
          }
        };
      } catch (error) {
        console.error(`NotificationContext: Error creating EventSource for ${sessionId}:`, error);
        setError(`Failed to connect: ${error}`);
        setIsConnected(false);
      }
    } else {
      console.log("NotificationContext: No session ID provided, skipping SSE connection.");
      setIsConnected(false);
      setLastMessage(null);
      setError(null);
    }

    // Cleanup function
    return () => {
      if (eventSource) {
        console.log(`NotificationContext: Closing SSE connection for session ${sessionId}`);
        eventSource.close();
        setIsConnected(false);
      }
    };
  }, [sessionId]); // Re-run effect if sessionId changes

  const contextValue = { lastMessage, isConnected, error };

  return (
    <NotificationContext.Provider value={contextValue}>
      {children}
    </NotificationContext.Provider>
  );
};

// Custom hook to use the notification context
export const useNotifications = (): NotificationContextType => {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
}; 
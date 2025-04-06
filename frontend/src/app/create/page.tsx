"use client";

import { useState, useEffect, useRef } from "react";
import { TranscriptionWebSocket } from "@/utils/websocket";
import { MicrophoneRecorder } from "@/utils/microphone";

export default function Create() {
  const [micPermission, setMicPermission] = useState<boolean | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState("Not connected");
  
  const wsRef = useRef<TranscriptionWebSocket | null>(null);
  const recorderRef = useRef<MicrophoneRecorder | null>(null);
  
  useEffect(() => {
    // Check for microphone permission on component mount
    checkMicrophonePermission();
    
    // Clean up resources when the component unmounts
    return () => {
      cleanupResources();
    };
  }, []);
  
  /**
   * Check for microphone permission
   */
  const checkMicrophonePermission = async () => {
    try {
      // Create temporary recorder to check permission
      const tempRecorder = new MicrophoneRecorder({
        chunkDurationMs: 5000,
        onChunkRecorded: () => {},
        onPermissionDenied: () => {
          setMicPermission(false);
          setError("Microphone access is required. Please allow access.");
        },
      });
      
      const hasPermission = await tempRecorder.checkPermission();
      setMicPermission(hasPermission);
      tempRecorder.cleanup();
    } catch (error) {
      setMicPermission(false);
      setError(`Failed to check microphone permission: ${error}`);
    }
  };
  
  /**
   * Request microphone permission
   */
  const requestMicrophonePermission = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      // Create temporary recorder to request permission
      const tempRecorder = new MicrophoneRecorder({
        chunkDurationMs: 5000,
        onChunkRecorded: () => {},
        onPermissionDenied: () => {
          setMicPermission(false);
          setError("Microphone access denied. Please allow access to use this application.");
        },
      });
      
      const granted = await tempRecorder.requestPermission();
      setMicPermission(granted);
      tempRecorder.cleanup();
      
      if (!granted) {
        setError("Microphone permission is required to use this application.");
      }
    } catch (error) {
      setError(`Failed to request microphone permission: ${error}`);
    } finally {
      setIsLoading(false);
    }
  };
  
  /**
   * Connect to the WebSocket server
   */
  const handleConnectAndListen = async () => {
    // First check for microphone permission
    if (!micPermission) {
      await requestMicrophonePermission();
      if (!micPermission) {
        return; // Permission denied, can't proceed
      }
    }
    
    try {
      setIsLoading(true);
      setError(null);
      setConnectionStatus("Connecting...");
      
      // Create a new WebSocket instance
      wsRef.current = new TranscriptionWebSocket();
      
      // Connect to the WebSocket server
      await wsRef.current.connect(
        // onMessage callback
        (message) => {
          if (message.status === "success") {
            setTranscript((prev) => prev + " " + message.transcript);
          } else if (message.status === "error") {
            setError(`Server error: ${message.message}`);
          }
        },
        // onError callback (now receives string error)
        (errorMessage) => {
          console.log("WebSocket error received:", errorMessage);
          setError(`WebSocket error: ${errorMessage}`);
          setConnectionStatus("Connection error");
          setIsConnected(false);
          stopRecording();
        },
        // onClose callback
        (event) => {
          const reason = event.reason || (event.wasClean ? "Connection closed normally" : "Connection closed unexpectedly");
          const code = event.code;
          
          console.log(`WebSocket closed with code ${code}: ${reason}`);
          setConnectionStatus(`Disconnected (${reason})`);
          setIsConnected(false);
          setSessionId("");
          stopRecording();
          
          if (!event.wasClean) {
            setError(`Connection closed unexpectedly (code: ${code}${reason ? `, reason: ${reason}` : ''})`);
          }
        }
      );
      
      // Initialize the microphone recorder
      recorderRef.current = new MicrophoneRecorder({
        chunkDurationMs: 5000, // 5 seconds per chunk
        onChunkRecorded: (audioData, chunkNumber) => {
          if (wsRef.current && wsRef.current.isConnected) {
            try {
              console.log(`Sending audio chunk ${chunkNumber}...`);
              // Send the audio chunk through the WebSocket
              wsRef.current.sendAudioChunk(audioData);
              console.log(`Audio chunk ${chunkNumber} sent successfully`);
            } catch (error) {
              console.error(`Failed to send audio chunk ${chunkNumber}:`, error);
              setError(`Failed to send audio: ${error instanceof Error ? error.message : String(error)}`);
            }
          } else {
            console.warn(`Cannot send audio chunk ${chunkNumber}: WebSocket not connected`);
            const status = wsRef.current ? wsRef.current.connectionStatus : "Not initialized";
            setError(`Cannot send audio: WebSocket not connected (status: ${status})`);
            stopRecording();
          }
        },
        onError: (errorMsg) => {
          console.error("Microphone error:", errorMsg);
          setError(`Microphone error: ${errorMsg}`);
          stopRecording();
        },
        onPermissionDenied: () => {
          setError("Microphone permission denied");
          setMicPermission(false);
          cleanupResources();
        },
      });
      
      setIsConnected(true);
      setSessionId(wsRef.current.currentSessionId);
      setConnectionStatus("Connected");
      
      // Start recording immediately
      await startRecording();
      
    } catch (err) {
      console.error("Connection error:", err);
      setError(`Failed to connect: ${err instanceof Error ? err.message : String(err)}`);
      setConnectionStatus("Connection failed");
      cleanupResources();
    } finally {
      setIsLoading(false);
    }
  };
  
  /**
   * Start recording audio
   */
  const startRecording = async () => {
    if (!recorderRef.current) {
      setError("Recorder not initialized");
      return;
    }
    
    try {
      console.log("Starting recording...");
      const success = await recorderRef.current.startRecording();
      if (success) {
        console.log("Recording started successfully");
        setIsRecording(true);
      } else {
        console.error("Failed to start recording");
        setError("Failed to start recording");
      }
    } catch (error) {
      console.error("Recording error:", error);
      setError(`Recording error: ${error}`);
    }
  };
  
  /**
   * Stop recording audio
   */
  const stopRecording = () => {
    if (recorderRef.current) {
      console.log("Stopping recording...");
      recorderRef.current.stopRecording();
      setIsRecording(false);
    }
  };
  
  /**
   * Handle the Listen/Stop button click
   */
  const handleListenButtonClick = async () => {
    if (isRecording) {
      // If already recording, stop recording
      stopRecording();
    } else {
      if (isConnected) {
        // If connected but not recording, start recording
        await startRecording();
      } else {
        // If not connected, connect and start recording
        await handleConnectAndListen();
      }
    }
  };
  
  /**
   * Disconnect from WebSocket and stop recording
   */
  const handleDisconnect = () => {
    cleanupResources();
  };
  
  /**
   * Clean up all resources
   */
  const cleanupResources = () => {
    // Stop recording
    if (recorderRef.current) {
      recorderRef.current.cleanup();
      recorderRef.current = null;
    }
    
    // Close WebSocket connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setIsRecording(false);
    setIsConnected(false);
    setSessionId("");
    setConnectionStatus("Not connected");
  };
  
  return (
    <main className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">Asha Transcription</h1>
        
        <div className="mb-8">
          {micPermission === false && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
              <p className="font-bold">Microphone Access Required</p>
              <p>This application needs access to your microphone to work.</p>
              <button
                onClick={requestMicrophonePermission}
                className="mt-2 bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded"
              >
                Grant Microphone Permission
              </button>
            </div>
          )}
          
          <div className="flex space-x-4 mb-4">
            <button
              onClick={handleListenButtonClick}
              disabled={isLoading || micPermission === false}
              className={`px-6 py-3 rounded-lg font-medium text-lg ${
                isRecording
                  ? "bg-red-500 hover:bg-red-600 text-white"
                  : "bg-blue-500 hover:bg-blue-600 text-white"
              } ${(isLoading || micPermission === false) ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              {isRecording ? "Stop Listening" : "Listen"}
            </button>
            
            {isConnected && (
              <button
                onClick={handleDisconnect}
                disabled={isLoading}
                className={`px-4 py-2 rounded font-medium ${
                  isLoading
                    ? "bg-gray-300 cursor-not-allowed"
                    : "bg-gray-500 text-white hover:bg-gray-600"
                }`}
              >
                Disconnect
              </button>
            )}
          </div>
          
          {isLoading && (
            <div className="flex items-center space-x-2 text-gray-600">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
              <span>Processing...</span>
            </div>
          )}
          
          {connectionStatus && connectionStatus !== "Connected" && connectionStatus !== "Not connected" && (
            <div className="mt-2">
              <span className="font-semibold">Status:</span> {connectionStatus}
            </div>
          )}
          
          {error && (
            <div className="text-red-500 mt-2 p-2 bg-red-50 border border-red-200 rounded">
              <p className="font-semibold">Error:</p>
              <p>{error}</p>
            </div>
          )}
          
          {sessionId && (
            <div className="mt-2">
              <span className="font-semibold">Session ID:</span> {sessionId}
            </div>
          )}
          
          {isRecording && (
            <div className="mt-2 flex items-center">
              <span className="bg-red-500 h-3 w-3 rounded-full mr-2 animate-pulse"></span>
              <span className="text-gray-700">Recording in progress...</span>
            </div>
          )}
        </div>
        
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
          <h2 className="text-xl font-semibold mb-3">Transcript</h2>
          <div className="min-h-[300px] p-4 bg-white rounded border border-gray-200">
            {transcript ? (
              <p className="whitespace-pre-wrap">{transcript}</p>
            ) : (
              <p className="text-gray-400 italic">
                No transcript available yet. Click "Listen" to start transcribing.
              </p>
            )}
          </div>
        </div>
      </div>
    </main>
  );
} 
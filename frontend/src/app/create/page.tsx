"use client";

import { useState, useEffect, useRef, FormEvent } from "react";
import { TranscriptionWebSocket } from "@/utils/websocket";
import { MicrophoneRecorder } from "@/utils/microphone";
import { Navigation } from "@/components/Navigation";

export default function Create() {
  const [micPermission, setMicPermission] = useState<boolean | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [sessionName, setSessionName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState("Not connected");
  const [step, setStep] = useState<"setup" | "transcription">("setup");
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [isCleaningUp, setIsCleaningUp] = useState(false);
  const [isClient, setIsClient] = useState(false);
  const [isInsecureContext, setIsInsecureContext] = useState(false);
  
  const wsRef = useRef<TranscriptionWebSocket | null>(null);
  const recorderRef = useRef<MicrophoneRecorder | null>(null);
  const isPausedRef = useRef(false);
  const isRecordingRef = useRef(false);
  
  // Keep the refs in sync with the states
  useEffect(() => {
    isPausedRef.current = isPaused;
  }, [isPaused]);
  
  useEffect(() => {
    isRecordingRef.current = isRecording;
  }, [isRecording]);
  
  useEffect(() => {
    setIsClient(true);
    
    // Check if we're in an insecure context that might need special handling
    if (typeof window !== 'undefined') {
      setIsInsecureContext(
        window.location.protocol === 'http:' && 
        !isLocalhost()
      );
    }
  }, []);
  
  useEffect(() => {
    // Only run this on client side
    if (isClient) {
      // Check for microphone permission on component mount
      checkMicrophonePermission();
    }
    
    // Clean up resources when the component unmounts
    return () => {
      cleanupResources();
    };
  }, [isClient]);
  
  /**
   * Check for microphone permission
   */
  const checkMicrophonePermission = async () => {
    try {
      // Check if the API is available first
      if (!navigator?.mediaDevices || !navigator?.mediaDevices?.getUserMedia) {
        console.error("MediaDevices API not available");
        setMicPermission(false);
        
        // Provide more specific guidance for local development
        if (window.location.protocol === 'http:' && !isLocalhost()) {
          setError(
            "Your browser restricts microphone access on non-HTTPS connections. " +
            "For local development, please use 'localhost' instead of an IP address, " +
            "or run the app with HTTPS."
          );
        } else {
          setError(
            "Your browser doesn't support microphone access. " +
            "Please use a modern browser like Chrome, Firefox, or Edge."
          );
        }
        return;
      }
      
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
      console.error("Error checking microphone permission:", error);
      setMicPermission(false);
      setError(`${error instanceof Error ? error.message : "Failed to check microphone permission"}`);
    }
  };
  
  /**
   * Request microphone permission
   */
  const requestMicrophonePermission = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      // First check if the API is available
      if (!navigator?.mediaDevices || !navigator?.mediaDevices?.getUserMedia) {
        // Provide more specific guidance for local development
        if (window.location.protocol === 'http:' && !isLocalhost()) {
          setError(
            "Your browser restricts microphone access on non-HTTPS connections. " +
            "For local development, please use 'localhost' instead of an IP address, " +
            "or run the app with HTTPS."
          );
        } else {
          setError(
            "Your browser doesn't support microphone access. " +
            "Please use a modern browser like Chrome, Firefox, or Edge."
          );
        }
        setMicPermission(false);
        return;
      }

      // Try direct getUserMedia approach first to force permission dialog
      try {
        console.log("Directly requesting microphone access...");
        const directStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        // If we get here, permission was granted directly
        console.log("Microphone permission granted via direct request");
        
        // Clean up the stream we just created
        directStream.getTracks().forEach(track => track.stop());
        
        setMicPermission(true);
        setIsLoading(false);
        return;
      } catch (directError) {
        console.error("Direct permission request failed:", directError);
        // Continue with the normal approach
      }
      
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
      console.error("Error in microphone permission request:", error);
      setError(`${error instanceof Error ? error.message : "Failed to request microphone permission"}`);
      setMicPermission(false);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Check if we're running on localhost
   */
  const isLocalhost = (): boolean => {
    return (
      window.location.hostname === 'localhost' || 
      window.location.hostname === '127.0.0.1' ||
      window.location.hostname.startsWith('192.168.') ||
      window.location.hostname.startsWith('10.0.')
    );
  };

  /**
   * Create a new session via API
   */
  const createSession = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const patientName = sessionName.trim() || "Patient Visit";
      
      // If we're in an insecure context or don't have mic permission yet,
      // try requesting it now before creating the session
      if ((micPermission === false || isInsecureContext) && navigator?.mediaDevices?.getUserMedia) {
        console.log("Attempting to get microphone permission before creating session...");
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          stream.getTracks().forEach(track => track.stop());
          setMicPermission(true);
        } catch (micError) {
          console.error("Could not get microphone permission:", micError);
          // Continue anyway - the user clicked start deliberately
        }
      }
      
      const response = await fetch("/backend/api/sessions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: patientName
        }),
      });
      
      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${await response.text()}`);
      }
      
      const data = await response.json();
      setSessionId(data.session_id);
      setSessionName(patientName);
      
      // Move to transcription step
      setStep("transcription");
      
      // Connect to WebSocket with the new session ID
      await handleConnectAndListen(data.session_id);
      
    } catch (error) {
      console.error("Failed to create session:", error);
      setError(`Failed to create session: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    createSession();
  };
  
  /**
   * Connect to the WebSocket server
   */
  const handleConnectAndListen = async (sessionId: string) => {
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
      
      console.log(`Attempting to establish WebSocket connection for session: ${sessionId}`);
      
      // Create a new WebSocket instance with the provided session ID
      // Use a relative WebSocket URL (automatically prefixed with ws:// or wss:// based on current protocol)
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/backend`;
      console.log(`Creating WebSocket with URL: ${wsUrl}`);
      
      wsRef.current = new TranscriptionWebSocket(wsUrl, sessionId);
      
      // Connect to the WebSocket server
      console.log("Connecting to WebSocket server...");
      
      // Attempt to connect with a retry if needed
      let connectAttempts = 0;
      const maxConnectAttempts = 2;
      
      while (connectAttempts < maxConnectAttempts) {
        try {
          connectAttempts++;
          
          await wsRef.current.connect(
            // onMessage callback
            (message) => {
              console.log("Received WebSocket message:", message);
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
          
          console.log("WebSocket connected successfully");
          break; // Connection successful, break out of retry loop
          
        } catch (connErr) {
          console.error(`WebSocket connection attempt ${connectAttempts} failed:`, connErr);
          
          if (connectAttempts >= maxConnectAttempts) {
            throw new Error(`Failed to connect after ${maxConnectAttempts} attempts: ${connErr instanceof Error ? connErr.message : String(connErr)}`);
          }
          
          console.log(`Retrying connection (attempt ${connectAttempts + 1}/${maxConnectAttempts})...`);
          // Short delay before retry
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      }
      
      // Verify the websocket connection before proceeding
      if (!wsRef.current || !wsRef.current.isConnected) {
        throw new Error("WebSocket connection verification failed");
      }
      
      // Update connection state
      setIsConnected(true);
      setSessionId(wsRef.current.currentSessionId);
      setConnectionStatus("Connected");
      
      console.log("Initializing microphone recorder...");
      
      // Initialize the microphone recorder
      recorderRef.current = new MicrophoneRecorder({
        chunkDurationMs: 5000, // 5 seconds per chunk
        onChunkRecorded: (audioData, chunkNumber) => {
          // Don't send any audio if we're in a paused state, no longer recording, or cleanup is in progress
          if (isPausedRef.current || !isRecordingRef.current || isCleaningUp) {
            console.log(`Not sending audio chunk ${chunkNumber}: ${
              isPausedRef.current ? 'Recording paused' : 
              isCleaningUp ? 'Cleanup in progress' : 
              'Recording stopped'
            }`);
            return;
          }
          
          console.log(`Processing audio chunk ${chunkNumber} to send to WebSocket...`);
          
          // Use a more robust check for the WebSocket connection
          if (wsRef.current && wsRef.current.isConnected) {
            try {
              console.log(`Sending audio chunk ${chunkNumber}...`);
              // Send the audio chunk through the WebSocket
              wsRef.current.sendAudioChunk(audioData);
              console.log(`Audio chunk ${chunkNumber} sent successfully`);
            } catch (error) {
              console.error(`Failed to send audio chunk ${chunkNumber}:`, error);
              setError(`Failed to send audio: ${error instanceof Error ? error.message : String(error)}`);
              // Don't stop recording on every error
              if (String(error).includes("not connected") || String(error).includes("not initialized")) {
                stopRecording();
              }
            }
          } else {
            const status = wsRef.current ? wsRef.current.connectionStatus : "Not initialized";
            console.warn(`Cannot send audio chunk ${chunkNumber}: WebSocket not connected (status: ${status})`);
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
      
      // Short delay to ensure WebSocket is fully ready before starting to record
      await new Promise(resolve => setTimeout(resolve, 500));
      
      console.log("Starting recording...");
      // Start recording immediately
      await startRecording();
      console.log("Recording started successfully");
      
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
      // Set the state/ref before starting recording to ensure correct state during first chunk
      setIsRecording(true);
      isRecordingRef.current = true;
      setIsPaused(false);
      isPausedRef.current = false;
      
      const success = await recorderRef.current.startRecording();
      if (success) {
        console.log("Recording started successfully");
      } else {
        console.error("Failed to start recording");
        setError("Failed to start recording");
        setIsRecording(false);
        isRecordingRef.current = false;
      }
    } catch (error) {
      console.error("Recording error:", error);
      setError(`Recording error: ${error}`);
      setIsRecording(false);
      isRecordingRef.current = false;
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
      isRecordingRef.current = false;
      setIsPaused(false);
      isPausedRef.current = false;
    }
  };
  
  /**
   * Toggle pause state
   */
  const togglePause = async () => {
    if (!recorderRef.current) return;
    
    if (isPaused) {
      // Resuming recording - start a new chunk
      console.log('Resuming recording...');
      setIsPaused(false);
      isPausedRef.current = false;
      
      // Only restart recording if we were previously recording
      if (isRecording) {
        await recorderRef.current.startRecording();
      }
    } else {
      // Pausing recording - stop the current recorder
      console.log('Pausing recording...');
      setIsPaused(true);
      isPausedRef.current = true;
      
      // Stop current recording but stay in recording state
      if (isRecording && recorderRef.current) {
        recorderRef.current.stopRecording();
      }
    }
  };
  
  /**
   * Handle the finish session confirmation
   */
  const handleFinishSession = () => {
    setShowConfirmation(true);
  };
  
  /**
   * Confirm ending the session
   */
  const confirmFinishSession = () => {
    cleanupResources();
    setShowConfirmation(false);
    setStep("setup");
    setTranscript("");
  };
  
  /**
   * Cancel session ending
   */
  const cancelFinishSession = () => {
    setShowConfirmation(false);
  };
  
  /**
   * Clean up all resources
   */
  const cleanupResources = () => {
    // Prevent multiple cleanup attempts
    if (isCleaningUp) {
      console.log("Cleanup already in progress, skipping duplicate call");
      return;
    }
    
    console.log("Starting resource cleanup...");
    
    // Immediately update all state values to prevent any further actions
    setIsCleaningUp(true);
    setIsRecording(false);
    isRecordingRef.current = false;
    setIsPaused(false);
    isPausedRef.current = false;
    setIsConnected(false);
    
    console.log("Updated all state values for cleanup");
    
    // Stop recording first to prevent any new audio chunks from being generated
    if (recorderRef.current) {
      console.log("Stopping recording...");
      recorderRef.current.stopRecording();
      
      // Add a small delay to ensure any in-progress chunks are processed
      setTimeout(() => {
        try {
          console.log("Cleaning up microphone resources...");
          if (recorderRef.current) {
            recorderRef.current.cleanup();
            recorderRef.current = null;
          }
          
          // Only close the WebSocket after recorder is fully cleaned up
          console.log("Closing WebSocket connection...");
          if (wsRef.current) {
            try {
              wsRef.current.close();
            } catch (err) {
              console.error("Error closing WebSocket:", err);
            }
            wsRef.current = null;
          }
        } catch (err) {
          console.error("Error during cleanup:", err);
        } finally {
          console.log("Cleanup complete");
          setSessionId("");
          setConnectionStatus("Not connected");
          setIsCleaningUp(false);
        }
      }, 300); // Increase the delay to give more time for cleanup
    } else {
      // If no recorder, just close the WebSocket
      console.log("No recorder to clean up, closing WebSocket...");
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch (err) {
          console.error("Error closing WebSocket:", err);
        }
        wsRef.current = null;
      }
      
      console.log("Cleanup complete");
      setSessionId("");
      setConnectionStatus("Not connected");
      setIsCleaningUp(false);
    }
  };
  
  // Setup step - collect session name
  if (step === "setup") {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        
        <main className="flex items-center justify-center p-8">
          <div className="max-w-md mx-auto">
            <h1 className="text-3xl font-bold mb-6 text-center text-blue-700">New Patient Encounter</h1>
            
            {(micPermission === false || isInsecureContext) && (
              <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
                <p className="font-bold">Microphone Access Required</p>
                <p>
                  {isInsecureContext 
                    ? "Your browser restricts microphone access on non-HTTPS connections. For local development, use 'localhost' instead of an IP address, or run with HTTPS."
                    : "This application needs access to your microphone to work."}
                </p>
                <button
                  onClick={requestMicrophonePermission}
                  disabled={isLoading}
                  className={`mt-2 bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded 
                             ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {isLoading ? 'Requesting access...' : 'Grant Microphone Access'}
                </button>
              </div>
            )}
            
            <form onSubmit={handleSubmit} className="bg-white p-6 rounded-lg shadow-md">
              <div className="mb-6">
                <label htmlFor="sessionName" className="block text-gray-700 font-medium mb-2">
                  Patient Name
                </label>
                <input
                  type="text"
                  id="sessionName"
                  value={sessionName}
                  onChange={(e) => setSessionName(e.target.value)}
                  placeholder="Enter patient name"
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-sm text-gray-500 mt-1">This will be used to identify the session</p>
              </div>
              
              <button
                type="submit"
                disabled={isLoading}
                className={`w-full px-6 py-3 rounded-lg font-medium text-lg bg-blue-600 hover:bg-blue-700 text-white
                  ${isLoading ? "opacity-50 cursor-not-allowed" : ""}`}
              >
                {isLoading ? "Starting session..." : "Begin Patient Encounter"}
              </button>
              
              {error && (
                <div className="text-red-500 mt-4 p-2 bg-red-50 border border-red-200 rounded">
                  <p className="font-semibold">Error:</p>
                  <p>{error}</p>
                </div>
              )}
            </form>
            
            {isInsecureContext && (
              <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-md text-yellow-800 text-sm">
                <p className="font-semibold mb-1">⚠️ Local Development on HTTP</p>
                <p>
                  You're running this app over HTTP, which may cause issues with microphone access.
                  For reliable microphone access, use one of these approaches:
                </p>
                <ul className="list-disc list-inside mt-2 space-y-1">
                  <li>Access the app using <strong>localhost</strong> instead of an IP address</li>
                  <li>Set up HTTPS locally with a self-signed certificate</li>
                  <li>Run your app with <code className="bg-yellow-100 px-1 rounded">HTTPS=true npm start</code> if using Create React App</li>
                  <li>For Next.js, use <code className="bg-yellow-100 px-1 rounded">next dev --experimental-https</code></li>
                </ul>
              </div>
            )}
          </div>
        </main>
      </div>
    );
  }
  
  // Transcription step - show the transcription interface
  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      
      <main className="p-8">
        <div className="max-w-4xl mx-auto">
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-2xl font-bold text-blue-700">
              {sessionName && sessionName !== "Patient Visit" 
                ? `Patient: ${sessionName}`
                : "Patient Encounter"}
            </h1>
            
            {isRecording && (
              <div className="flex items-center">
                {isPaused ? (
                  <div className="flex items-center">
                    <span className="bg-yellow-500 h-3 w-3 rounded-full mr-2"></span>
                    <span className="text-gray-700 mr-4">Recording paused</span>
                  </div>
                ) : (
                  <div className="flex items-center">
                    <span className="bg-red-500 h-3 w-3 rounded-full mr-2 animate-pulse"></span>
                    <span className="text-gray-700 mr-4">Recording in progress</span>
                  </div>
                )}
              </div>
            )}
          </div>
          
          <div className="mb-6 flex flex-wrap gap-3">
            {(micPermission === false || isInsecureContext) && (
              <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4 w-full">
                <p className="font-bold">Microphone Access Required</p>
                <p>
                  {isInsecureContext 
                    ? "Your browser restricts microphone access on non-HTTPS connections. For local development, use 'localhost' instead of an IP address, or run with HTTPS."
                    : "This application needs access to your microphone to work."}
                </p>
                <button
                  onClick={requestMicrophonePermission}
                  disabled={isLoading}
                  className={`mt-2 bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded 
                            ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {isLoading ? 'Requesting access...' : 'Grant Microphone Access'}
                </button>
              </div>
            )}
            
            {isConnected && (
              <>
                {isRecording && (
                  <button
                    onClick={togglePause}
                    className={`px-6 py-3 rounded-md font-medium ${
                      isPaused
                        ? "bg-green-600 hover:bg-green-700 text-white"
                        : "bg-yellow-500 hover:bg-yellow-600 text-white"
                    }`}
                  >
                    {isPaused ? "Resume Recording" : "Pause Recording"} 
                  </button>
                )}
                
                <button
                  onClick={handleFinishSession}
                  className="px-6 py-3 rounded-md font-medium bg-red-600 hover:bg-red-700 text-white"
                >
                  Finish Session
                </button>
              </>
            )}
            
            {isLoading && (
              <div className="flex items-center space-x-2 text-gray-600">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
                <span>Processing...</span>
              </div>
            )}
            
            {error && (
              <div className="text-red-500 mt-2 p-2 bg-red-50 border border-red-200 rounded w-full">
                <p className="font-semibold">Error:</p>
                <p>{error}</p>
              </div>
            )}
          </div>
          
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
            <h2 className="text-xl font-semibold mb-4 text-blue-700">Consultation Transcript</h2>
            <div className="min-h-[350px] p-5 bg-gray-50 rounded border border-gray-200">
              {transcript ? (
                <p className="whitespace-pre-wrap text-gray-800">{transcript}</p>
              ) : (
                <p className="text-gray-400 italic">
                  No transcript available yet. The system will automatically record and transcribe the conversation.
                </p>
              )}
            </div>
          </div>
        </div>
      </main>
      
      {/* Confirmation Dialog */}
      {showConfirmation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-xl font-bold mb-4">End Patient Session?</h3>
            <p className="mb-6">
              Are you sure you want to end this session? This will stop the recording and save the transcript.
            </p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={cancelFinishSession}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmFinishSession}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
              >
                End Session
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 
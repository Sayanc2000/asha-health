/**
 * Provides functionality for recording audio from the microphone in chunks
 */

export interface RecordingOptions {
  minChunkDurationMs: number;
  maxChunkDurationMs: number;
  silenceDurationMs: number;
  silenceThresholdDb: number;
  onChunkRecorded: (audioData: string, chunkNumber: number) => void;
  onError?: (error: string) => void;
  onPermissionDenied?: () => void;
}

/**
 * Checks if the current environment is considered secure for media access
 * (either HTTPS or localhost)
 */
function isSecureContext(): boolean {
  // Check if we're in a secure context (HTTPS)
  if (window.isSecureContext) {
    return true;
  }
  
  // Also allow localhost for development
  const isLocalhost = 
    window.location.hostname === 'localhost' || 
    window.location.hostname === '127.0.0.1' ||
    window.location.hostname.startsWith('192.168.') ||
    window.location.hostname.startsWith('10.0.');
    
  return isLocalhost;
}

export class MicrophoneRecorder {
  private stream: MediaStream | null = null;
  private mediaRecorder: MediaRecorder | null = null;
  private audioContext: AudioContext | null = null;
  private analyserNode: AnalyserNode | null = null;
  private audioSourceNode: MediaStreamAudioSourceNode | null = null;
  private chunkCounter: number = 0;
  private analysisInterval: NodeJS.Timeout | null = null;
  private isRecording: boolean = false;
  private options: RecordingOptions;
  private currentChunkStartTime: number = 0;
  private silenceStartTime: number = 0;
  private isSilent: boolean = false;
  private currentAudioChunks: Blob[] = [];

  constructor(options: RecordingOptions) {
    this.options = options;
  }

  /**
   * Request microphone permission and initialize recorder
   */
  async requestPermission(): Promise<boolean> {
    try {
      console.log('Requesting microphone permission...');
      
      // Check if mediaDevices API is available
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.error('MediaDevices API not available in this browser or context');
        
        // Check if we're in a non-secure context that's not localhost
        if (!isSecureContext()) {
          throw new Error(
            'Media devices require a secure context (HTTPS) in production. ' +
            'For local development, try using localhost instead of an IP address.'
          );
        } else {
          throw new Error('Media devices not supported in this browser.');
        }
      }
      
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log('Microphone permission granted');
      
      // Make sure we create a new MediaStream instance to ensure permissions are properly applied
      if (this.stream) {
        // Stop any existing tracks before creating new ones
        this.stream.getTracks().forEach(track => track.stop());
      }
      
      // Re-request the stream to ensure we have fresh permissions
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      return true;
    } catch (error) {
      console.error('Error accessing microphone:', error);
      if (this.options.onPermissionDenied) {
        this.options.onPermissionDenied();
      }
      return false;
    }
  }

  /**
   * Check if microphone permission is granted
   */
  async checkPermission(): Promise<boolean> {
    try {
      console.log('Checking microphone permission status...');
      
      // Check if mediaDevices API is available
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.error('MediaDevices API not available in this browser or context');
        
        // Check if we're in a non-secure context that's not localhost
        if (!isSecureContext()) {
          throw new Error(
            'Media devices require a secure context (HTTPS) in production. ' +
            'For local development, try using localhost instead of an IP address.'
          );
        } else {
          throw new Error('Media devices not supported in this browser.');
        }
      }
      
      // Try permissions API first
      try {
        const permissionStatus = await navigator.permissions.query({ name: 'microphone' as PermissionName });
        console.log('Microphone permission status:', permissionStatus.state);
        
        // Listen for permission changes
        permissionStatus.addEventListener('change', () => {
          console.log('Permission status changed to:', permissionStatus.state);
          if (permissionStatus.state === 'granted' && !this.isRecording) {
            // If permission was just granted, we might want to initialize the stream
            this.initializeStream();
          }
        });
        
        return permissionStatus.state === 'granted';
      } catch (permError) {
        console.warn('Browser does not support permission query, falling back to getUserMedia check:', permError);
        // Fallback for browsers that don't support permission query
        return this.requestPermission();
      }
    } catch (error) {
      console.error('Error checking microphone permission:', error);
      return false;
    }
  }

  /**
   * Initialize the audio stream
   */
  private async initializeStream(): Promise<boolean> {
    if (!this.stream) {
      try {
        console.log('Initializing audio stream...');
        this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        return true;
      } catch (error) {
        console.error('Failed to initialize microphone:', error);
        if (this.options.onError) {
          this.options.onError('Failed to initialize microphone');
        }
        return false;
      }
    }
    return true;
  }

  /**
   * Start recording audio in chunks of specified duration
   */
  async startRecording(): Promise<boolean> {
    if (this.isRecording) {
      console.log('Already recording, not starting again');
      return true;
    }

    // Request permission if not already granted
    const hasPermission = await this.checkPermission();
    if (!hasPermission) {
      console.log('No microphone permission, requesting...');
      const permissionGranted = await this.requestPermission();
      if (!permissionGranted) {
        console.error('Microphone permission denied');
        return false;
      }
    }

    // Initialize audio stream if not already done
    const streamInitialized = await this.initializeStream();
    if (!streamInitialized) {
      return false;
    }

    // Initialize audio context and nodes
    this.audioContext = new AudioContext();
    this.analyserNode = this.audioContext.createAnalyser();
    this.analyserNode.fftSize = 2048;
    this.audioSourceNode = this.audioContext.createMediaStreamSource(this.stream!);
    this.audioSourceNode.connect(this.analyserNode);

    this.isRecording = true;
    this.chunkCounter = 0;
    this.currentChunkStartTime = Date.now();
    this.silenceStartTime = 0;
    this.isSilent = false;
    this.currentAudioChunks = [];

    console.log(`Starting recording with dynamic chunking (min: ${this.options.minChunkDurationMs}ms, max: ${this.options.maxChunkDurationMs}ms)`);
    
    // Start the first recording session
    this.startNewRecordingSession();
    
    // Start the analysis loop
    this.analysisInterval = setInterval(() => {
      this.analyzeAudio();
    }, 100); // Check every 100ms

    return true;
  }

  /**
   * Start a new recording session
   */
  private startNewRecordingSession(): void {
    if (!this.stream) {
      console.error('No audio stream available');
      if (this.options.onError) {
        this.options.onError('No audio stream available');
      }
      return;
    }

    this.mediaRecorder = new MediaRecorder(this.stream);
    this.currentAudioChunks = [];
    
    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        this.currentAudioChunks.push(event.data);
      }
    };

    this.mediaRecorder.onstop = () => {
      this.processAndSendChunk();
    };

    this.mediaRecorder.start();
    this.currentChunkStartTime = Date.now();
    this.silenceStartTime = 0;
    this.isSilent = false;
  }

  /**
   * Analyze audio for silence detection
   */
  private analyzeAudio(): void {
    if (!this.analyserNode || !this.isRecording) return;

    const bufferLength = this.analyserNode.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    this.analyserNode.getByteFrequencyData(dataArray);

    // Calculate RMS volume in dBFS
    let sum = 0;
    for (let i = 0; i < bufferLength; i++) {
      sum += dataArray[i] * dataArray[i];
    }
    const rms = Math.sqrt(sum / bufferLength);
    const volumeDb = 20 * Math.log10(rms / 255);

    const now = Date.now();
    const chunkDuration = now - this.currentChunkStartTime;

    // Update silence state
    if (volumeDb > this.options.silenceThresholdDb) {
      this.isSilent = false;
      this.silenceStartTime = 0;
    } else if (!this.isSilent) {
      this.isSilent = true;
      this.silenceStartTime = now;
    }

    // Check if we should finalize the current chunk
    const silenceDuration = this.isSilent ? now - this.silenceStartTime : 0;
    const shouldFinalize = 
      (this.isSilent && 
       silenceDuration >= this.options.silenceDurationMs && 
       chunkDuration >= this.options.minChunkDurationMs) ||
      (chunkDuration >= this.options.maxChunkDurationMs);

    if (shouldFinalize && this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }
  }

  /**
   * Process and send the current audio chunk
   */
  private processAndSendChunk(): void {
    const chunkNumber = this.chunkCounter++;
    
    try {
      if (this.currentAudioChunks.length === 0) {
        console.warn(`Chunk ${chunkNumber} has no audio data`);
        return;
      }
      
      console.log(`Processing recorded chunk ${chunkNumber} (${this.currentAudioChunks.length} chunks)`);
      
      // Create a blob from the recorded chunks
      const audioBlob = new Blob(this.currentAudioChunks, { type: 'audio/wav' });
      console.log(`Chunk ${chunkNumber} size: ${audioBlob.size} bytes`);
      
      // Convert to base64
      const reader = new FileReader();
      reader.readAsDataURL(audioBlob);
      reader.onloadend = () => {
        if (typeof reader.result === 'string') {
          // Extract the base64 part (remove the data:audio/wav;base64, prefix)
          const base64Audio = reader.result.split(',')[1];
          console.log(`Chunk ${chunkNumber} converted to base64 (length: ${base64Audio.length})`);
          this.options.onChunkRecorded(base64Audio, chunkNumber);
          
          // Start a new recording session
          this.startNewRecordingSession();
        } else {
          console.error(`Failed to convert chunk ${chunkNumber} to string`);
          if (this.options.onError) {
            this.options.onError(`Failed to process audio: Invalid data format`);
          }
        }
      };
    } catch (error) {
      console.error(`Failed to process chunk ${chunkNumber}:`, error);
      if (this.options.onError) {
        this.options.onError(`Failed to process audio chunk: ${error}`);
      }
    }
  }

  /**
   * Stop recording audio
   */
  stopRecording(): void {
    console.log('Stopping all recording');
    
    if (this.analysisInterval) {
      clearInterval(this.analysisInterval);
      this.analysisInterval = null;
    }

    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }

    this.isRecording = false;
  }

  /**
   * Clean up resources
   */
  cleanup(): void {
    console.log('Cleaning up microphone recorder resources');
    this.stopRecording();
    
    // Disconnect audio nodes
    if (this.audioSourceNode) {
      this.audioSourceNode.disconnect();
      this.audioSourceNode = null;
    }
    if (this.analyserNode) {
      this.analyserNode.disconnect();
      this.analyserNode = null;
    }

    // Stop and clean up stream
    if (this.stream) {
      this.stream.getTracks().forEach(track => {
        console.log(`Stopping audio track: ${track.kind}`);
        track.stop();
      });
      this.stream = null;
    }

    // Close audio context
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }
}

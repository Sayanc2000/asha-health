/**
 * Provides functionality for recording audio from the microphone in chunks
 */

export interface RecordingOptions {
  chunkDurationMs: number;
  onChunkRecorded: (audioData: string, chunkNumber: number) => void;
  onError?: (error: string) => void;
  onPermissionDenied?: () => void;
}

export class MicrophoneRecorder {
  private stream: MediaStream | null = null;
  private mediaRecorder: MediaRecorder | null = null;
  private audioContext: AudioContext | null = null;
  private chunkCounter: number = 0;
  private recordingInterval: NodeJS.Timeout | null = null;
  private isRecording: boolean = false;
  private options: RecordingOptions;

  constructor(options: RecordingOptions) {
    this.options = options;
  }

  /**
   * Request microphone permission and initialize recorder
   */
  async requestPermission(): Promise<boolean> {
    try {
      console.log('Requesting microphone permission...');
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log('Microphone permission granted');
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
      const permissionStatus = await navigator.permissions.query({ name: 'microphone' as PermissionName });
      console.log('Microphone permission status:', permissionStatus.state);
      return permissionStatus.state === 'granted';
    } catch (error) {
      console.warn('Browser does not support permission query, falling back to getUserMedia check');
      // Fallback for browsers that don't support permission query
      return this.requestPermission();
    }
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
    if (!this.stream) {
      try {
        console.log('Initializing audio stream...');
        this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (error) {
        console.error('Failed to initialize microphone:', error);
        if (this.options.onError) {
          this.options.onError('Failed to initialize microphone');
        }
        return false;
      }
    }

    // Initialize audio context
    this.audioContext = new AudioContext();
    this.isRecording = true;
    this.chunkCounter = 0;

    console.log(`Starting recording with ${this.options.chunkDurationMs}ms chunks`);
    
    // Set up chunk recording at the specified interval
    this.recordChunk();
    this.recordingInterval = setInterval(() => {
      this.recordChunk();
    }, this.options.chunkDurationMs);

    return true;
  }

  /**
   * Record a single audio chunk
   */
  private recordChunk(): void {
    // If already recording, stop the current chunk before starting a new one
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }

    const chunkNumber = this.chunkCounter++;
    console.log(`Starting to record chunk ${chunkNumber}`);
    
    if (!this.stream) {
      console.error('No audio stream available');
      if (this.options.onError) {
        this.options.onError('No audio stream available');
      }
      return;
    }

    // Initialize media recorder for this chunk
    this.mediaRecorder = new MediaRecorder(this.stream);
    
    const audioChunks: Blob[] = [];
    
    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    this.mediaRecorder.onstop = async () => {
      try {
        if (audioChunks.length === 0) {
          console.warn(`Chunk ${chunkNumber} has no audio data`);
          return;
        }
        
        console.log(`Processing recorded chunk ${chunkNumber} (${audioChunks.length} chunks)`);
        
        // Create a blob from the recorded chunks
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
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
    };

    // Start recording this chunk
    this.mediaRecorder.start();
    
    // Stop after the chunk duration (slightly less to allow for processing)
    setTimeout(() => {
      if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
        console.log(`Stopping chunk ${chunkNumber} recording`);
        this.mediaRecorder.stop();
      }
    }, this.options.chunkDurationMs - 100);
  }

  /**
   * Stop recording audio
   */
  stopRecording(): void {
    console.log('Stopping all recording');
    
    if (this.recordingInterval) {
      clearInterval(this.recordingInterval);
      this.recordingInterval = null;
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
    
    if (this.stream) {
      this.stream.getTracks().forEach(track => {
        console.log(`Stopping audio track: ${track.kind}`);
        track.stop();
      });
      this.stream = null;
    }

    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }
}

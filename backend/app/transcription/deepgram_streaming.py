import asyncio
import json
import time
import uuid
import ssl
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from loguru import logger
import websockets
from dotenv import load_dotenv, find_dotenv

from app.store.storage import TranscriptSegment, get_transcript_store

find_dotenv()
load_dotenv()
class DeepgramStreamingService:
    """
    Service that provides real-time streaming transcription using Deepgram's WebSocket API.
    Manages a connection for a single client session.
    """
    
    def __init__(
        self, 
        api_key: str, 
        session_id: str, 
        client_websocket,  # FastAPI WebSocket object
        result_callback: Callable
    ):
        """
        Initialize the Deepgram streaming service.
        
        Args:
            api_key: Deepgram API key
            session_id: Unique session identifier
            client_websocket: FastAPI WebSocket object to send results back to client
            result_callback: Callback function to process transcription results
        """
        self.api_key = api_key
        self.session_id = session_id
        self.client_websocket = client_websocket
        self.result_callback = result_callback
        
        # WebSocket connection to Deepgram
        self._deepgram_ws = None
        
        # Background tasks
        self._receive_task = None
        self._keep_alive_task = None
        
        # State variables
        self._current_serial = 0
        self._is_connected = False
        
        logger.info(f"Session {session_id}: Created Deepgram streaming service")
    
    async def connect(self):
        """
        Establish connection to Deepgram's WebSocket API.
        
        Raises:
            Exception: If connection fails
        """
        if self._is_connected:
            logger.warning(f"Session {self.session_id}: Already connected to Deepgram")
            return
        
        # Construct the WebSocket URL with query parameters
        # Documentation: https://developers.deepgram.com/docs/transcription-parameters
        params = {
            "encoding": "linear16",  # Raw PCM audio
            "sample_rate": 16000,    # 16 kHz
            "channels": 1,           # Mono audio
            "language": "en",        # English
            "model": "nova-2",       # Enhanced model
            "tier": "enhanced",      # Enhanced tier
            "punctuate": True,       # Add punctuation
            "diarize": True,         # Speaker diarization
            "smart_format": True,    # Format numbers, dates, etc.
            "utterances": True,      # Segment into utterances
            "interim_results": True, # Get interim results
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items() if not isinstance(v, bool)] + 
                               [f"{k}=true" for k, v in params.items() if v is True])
        uri = f"wss://api.deepgram.com/v1/listen?{query_string}"
        
        try:
            # For websockets 15.0.1, we need to use a slightly different approach
            # Create a connection using the proper header format
            ssl_context = ssl.create_default_context()
            logger.info(f"Session {self.session_id}: Connecting to Deepgram streaming API with URI: {uri}, API Key: {self.api_key}")
            self._deepgram_ws = await websockets.connect(
                uri,
                additional_headers={"Authorization": f"token {self.api_key}"},
                ssl=ssl_context
            )
            
            # Start the receive loop and keep-alive loop as background tasks
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._keep_alive_task = asyncio.create_task(self._keep_alive_loop())
            
            self._is_connected = True
            logger.info(f"Session {self.session_id}: Connected to Deepgram streaming API")
        
        except Exception as e:
            logger.error(f"Session {self.session_id}: Failed to connect to Deepgram: {str(e)}")
            # Ensure tasks are cleaned up if connection fails
            await self.close()
            # Re-raise the exception
            raise
    
    async def send_audio(self, audio_chunk: bytes):
        """
        Send audio data to Deepgram.
        
        Args:
            audio_chunk: Raw audio bytes
            
        Raises:
            Exception: If the connection is closed or another error occurs
        """
        if not self._is_connected or not self._deepgram_ws:
            logger.error(f"Session {self.session_id}: Cannot send audio - not connected to Deepgram")
            return
        
        try:
            await self._deepgram_ws.send(audio_chunk)
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error sending audio to Deepgram: {str(e)}")
            # If the connection is broken, close everything
            if "closed" in str(e).lower():
                await self.close()
                raise
    
    async def _receive_loop(self):
        """
        Background task that receives and processes messages from Deepgram.
        """
        if not self._deepgram_ws:
            logger.error(f"Session {self.session_id}: WebSocket not initialized in receive loop")
            return
        
        try:
            async for message in self._deepgram_ws:
                # Parse the JSON message
                try:
                    response = json.loads(message)
                    await self._process_response(response)
                except json.JSONDecodeError as e:
                    logger.error(f"Session {self.session_id}: Failed to parse Deepgram message: {str(e)}")
                except Exception as e:
                    logger.error(f"Session {self.session_id}: Error processing Deepgram message: {str(e)}")
        
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Session {self.session_id}: Deepgram connection closed: {str(e)}")
        
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error in receive loop: {str(e)}")
        
        finally:
            # Ensure we clean up if the loop exits
            await self.close()
    
    async def _keep_alive_loop(self):
        """
        Background task that sends periodic keep-alive messages to Deepgram.
        """
        try:
            while self._is_connected and self._deepgram_ws:
                await asyncio.sleep(30)  # Send keep-alive every 30 seconds
                
                if self._is_connected and self._deepgram_ws:
                    try:
                        # Send an empty object as keep-alive
                        await self._deepgram_ws.send(json.dumps({"type": "KeepAlive"}))
                        logger.debug(f"Session {self.session_id}: Sent keep-alive to Deepgram")
                    except Exception as e:
                        logger.error(f"Session {self.session_id}: Failed to send keep-alive: {str(e)}")
                        break
        
        except asyncio.CancelledError:
            # Task was cancelled, exit gracefully
            pass
        
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error in keep-alive loop: {str(e)}")
    
    async def _process_response(self, response: Dict[str, Any]):
        """
        Process a response from Deepgram.
        
        Args:
            response: JSON response from Deepgram
        """
        # Check if this is a non-transcription message
        if "type" in response:
            if response["type"] == "MetadataMessage":
                logger.debug(f"Session {self.session_id}: Received metadata from Deepgram")
                return
            if response["type"] == "UtteranceEndMessage":
                logger.debug(f"Session {self.session_id}: Utterance ended")
                return
            if response["type"] == "Error":
                logger.error(f"Session {self.session_id}: Deepgram error: {response.get('error', 'Unknown error')}")
                return
        
        # Handle transcription results
        if "channel" in response and "alternatives" in response["channel"]:
            # Check if this is a final result
            is_final = not response.get("is_interim", True)
            
            # Get the transcript text from the first alternative
            alternatives = response["channel"]["alternatives"]
            if alternatives and len(alternatives) > 0:
                transcript_text = alternatives[0].get("transcript", "")
                
                # Process words and create segments with speaker information
                if "words" in alternatives[0]:
                    words = alternatives[0]["words"]
                    segments = []
                    
                    # Group words by speaker
                    current_speaker = None
                    current_segment = {"text": "", "words": []}
                    
                    for word in words:
                        speaker = word.get("speaker", "SPEAKER_00")
                        
                        # Start a new segment if speaker changes
                        if current_speaker is not None and current_speaker != speaker:
                            if current_segment["words"]:
                                segment_start = current_segment["words"][0].get("start", 0.0)
                                segment_end = current_segment["words"][-1].get("end", 0.0)
                                
                                segments.append({
                                    "id": len(segments),
                                    "start": segment_start,
                                    "end": segment_end,
                                    "text": current_segment["text"].strip(),
                                    "speaker": current_speaker
                                })
                            
                            # Reset for next segment
                            current_segment = {"text": "", "words": []}
                        
                        current_speaker = speaker
                        current_segment["text"] += word.get("punctuated_word", word.get("word", "")) + " "
                        current_segment["words"].append(word)
                    
                    # Add the last segment if there's any
                    if current_segment["words"]:
                        segment_start = current_segment["words"][0].get("start", 0.0)
                        segment_end = current_segment["words"][-1].get("end", 0.0)
                        
                        segments.append({
                            "id": len(segments),
                            "start": segment_start,
                            "end": segment_end,
                            "text": current_segment["text"].strip(),
                            "speaker": current_speaker
                        })
                    
                    # Extract unique speakers
                    speakers = list(set(segment["speaker"] for segment in segments))
                    
                    # Create the transcript data structure
                    transcript_data = {
                        "text": transcript_text,
                        "segments": segments,
                        "speakers": speakers,
                        "is_final": is_final
                    }
                    
                    # Increment serial number for final results
                    if is_final:
                        self._current_serial += 1
                    
                    # Call the callback function with the results
                    await self.result_callback(
                        session_id=self.session_id,
                        transcript_data=transcript_data,
                        is_final=is_final,
                        serial=self._current_serial if is_final else None
                    )
    
    async def close(self):
        """Close the connection to Deepgram and clean up resources."""
        # Cancel background tasks
        if self._receive_task:
            self._receive_task.cancel()
            self._receive_task = None
        
        if self._keep_alive_task:
            self._keep_alive_task.cancel()
            self._keep_alive_task = None
        
        # Close the WebSocket connection
        if self._deepgram_ws:
            try:
                await self._deepgram_ws.close()
                self._deepgram_ws = None
            except Exception as e:
                logger.error(f"Session {self.session_id}: Error closing Deepgram WebSocket: {str(e)}")
        
        self._is_connected = False
        logger.info(f"Session {self.session_id}: Closed Deepgram streaming connection") 
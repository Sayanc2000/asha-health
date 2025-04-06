import { readFile } from 'fs/promises';
import { NextResponse } from 'next/server';
import path from 'path';

export async function GET() {
  try {
    // Path to the audio file in the backend directory
    const filePath = path.resolve(process.cwd(), '../backend/audio_chunk_10s.wav');
    
    // Read the file as a buffer
    const buffer = await readFile(filePath);
    
    // Create a Response with the file data
    return new NextResponse(buffer, {
      headers: {
        'Content-Type': 'audio/wav',
        'Content-Disposition': 'inline; filename="audio_chunk_10s.wav"'
      }
    });
  } catch (error) {
    console.error('Error loading audio file:', error);
    return NextResponse.json(
      { error: 'Failed to load audio file' },
      { status: 500 }
    );
  }
} 
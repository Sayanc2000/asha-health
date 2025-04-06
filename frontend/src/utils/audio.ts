/**
 * Reads an audio file and returns a base64 encoded string
 * @param file - The audio file to read
 * @returns Promise that resolves with the base64 encoded string
 */
export const readAudioFile = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    
    reader.onload = (event) => {
      if (!event.target || !event.target.result) {
        reject(new Error('Failed to read file'));
        return;
      }
      
      const result = event.target.result;
      
      if (typeof result === 'string') {
        // If the result is already a string (might be the case for smaller files)
        resolve(result.split(',')[1]); // Remove the "data:audio/wav;base64," part
      } else {
        // If the result is an ArrayBuffer
        const bytes = new Uint8Array(result);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        const base64 = window.btoa(binary);
        resolve(base64);
      }
    };
    
    reader.onerror = () => {
      reject(new Error('Error reading file'));
    };
    
    reader.readAsDataURL(file);
  });
};

/**
 * Fetches an audio file from a URL and returns a base64 encoded string
 * @param url - The URL of the audio file
 * @returns Promise that resolves with the base64 encoded string
 */
export const fetchAudioFileAsBase64 = async (url: string): Promise<string> => {
  const response = await fetch(url);
  const blob = await response.blob();
  return await readAudioFile(new File([blob], 'audio.wav', { type: blob.type }));
}; 
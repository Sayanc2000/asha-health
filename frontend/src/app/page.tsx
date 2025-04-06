"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  
  useEffect(() => {
    // Redirect to the create page
    router.push("/create");
  }, [router]);
  
  return (
    <main className="min-h-screen flex items-center justify-center p-8">
      <div className="max-w-md mx-auto text-center">
        <h1 className="text-3xl font-bold mb-6">Asha Transcription</h1>
        <p className="mb-6">Redirecting to transcription page...</p>
        <button
          onClick={() => router.push("/create")}
          className="px-6 py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium text-lg"
        >
          Go to Transcription
        </button>
      </div>
    </main>
  );
} 
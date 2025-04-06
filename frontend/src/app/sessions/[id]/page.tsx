"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Navigation } from "@/components/Navigation";
import Link from "next/link";

interface Transcript {
  serial: number;
  transcript: string;
  speaker: string;
  created_at: string;
}

interface SessionData {
  session_id: string;
  name: string | null;
  created_at: string;
  transcripts: Transcript[];
}

interface SOAPNote {
  session_id: string;
  soap_text: string;
  created_at: string;
}

export default function SessionDetail() {
  const params = useParams();
  const sessionId = params.id as string;
  
  const [sessionData, setSessionData] = useState<SessionData | null>(null);
  const [soapNote, setSoapNote] = useState<SOAPNote | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSoapLoading, setIsSoapLoading] = useState(false);
  const [isGeneratingSoap, setIsGeneratingSoap] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [soapError, setSoapError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"transcript" | "soap">("transcript");

  useEffect(() => {
    if (sessionId) {
      fetchSessionData();
      fetchSoapNote();
    }
  }, [sessionId]);

  const fetchSessionData = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`/backend/api/sessions/${sessionId}`);

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${await response.text()}`);
      }

      const data = await response.json();
      setSessionData(data);
    } catch (error) {
      console.error("Failed to fetch session data:", error);
      setError(`Failed to fetch session data: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchSoapNote = async () => {
    try {
      setIsSoapLoading(true);
      setSoapError(null);

      const response = await fetch(`/backend/api/sessions/${sessionId}/soap`);

      if (response.status === 404) {
        // SOAP note does not exist yet
        setSoapNote(null);
        return;
      }

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${await response.text()}`);
      }

      const data = await response.json();
      setSoapNote(data);
      
      // If we successfully fetched a SOAP note and it's the first time, switch to the SOAP tab
      if (data && !soapNote) {
        setActiveTab("soap");
      }
    } catch (error) {
      console.error("Failed to fetch SOAP note:", error);
      // Don't set an error if it's just a 404
      if (!(error instanceof Error && error.message.includes("404"))) {
        setSoapError(`Failed to fetch SOAP note: ${error instanceof Error ? error.message : String(error)}`);
      }
    } finally {
      setIsSoapLoading(false);
    }
  };

  const generateSoapNote = async () => {
    try {
      setIsGeneratingSoap(true);
      setSoapError(null);

      const response = await fetch(`/backend/api/sessions/${sessionId}/soap`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${await response.text()}`);
      }

      const data = await response.json();
      setSoapNote(data);
      setActiveTab("soap");
    } catch (error) {
      console.error("Failed to generate SOAP note:", error);
      setSoapError(`Failed to generate SOAP note: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsGeneratingSoap(false);
    }
  };

  // Helper function to render formatted SOAP note
  const renderFormattedSoapNote = (soapText: string) => {
    if (!soapText) return null;
    
    // Add custom CSS for the SOAP note
    return (
      <div className="soap-note">
        <style jsx global>{`
          .soap-note h2 {
            font-size: 1.25rem;
            font-weight: 600;
            color: #374151;
            margin-top: 1.5rem;
            margin-bottom: 0.75rem;
          }
          .soap-note h2:first-child {
            margin-top: 0;
          }
          .soap-note ul {
            margin-top: 0.5rem;
            margin-bottom: 1.5rem;
            padding-left: 1.5rem;
            list-style-type: disc;
          }
          .soap-note li {
            margin-bottom: 0.5rem;
            line-height: 1.5;
          }
          .soap-note li span {
            color: #1F2937;
          }
          .soap-note li span:hover {
            text-decoration: underline;
            cursor: help;
          }
        `}</style>
        <div 
          className="prose max-w-none"
          dangerouslySetInnerHTML={{ __html: soapText }}
        />
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="mb-6">
            <Link
              href="/sessions"
              className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back to sessions
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">
              {sessionData?.name || `Session ${sessionId.split('-')[0]}`}
            </h1>
          </div>

          {isLoading && (
            <div className="flex justify-center items-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
              <span className="ml-2 text-gray-600">Loading session data...</span>
            </div>
          )}

          {error && (
            <div className="bg-red-50 p-4 rounded-md border border-red-200 mb-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-red-800">Error</h3>
                  <div className="mt-2 text-sm text-red-700">
                    <p>{error}</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {!isLoading && !error && sessionData && (
            <>
              <div className="bg-white shadow overflow-hidden sm:rounded-lg mb-6">
                <div className="px-4 py-5 border-b border-gray-200 sm:px-6">
                  <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
                    <div className="sm:col-span-1">
                      <dt className="text-sm font-medium text-gray-500">Created At</dt>
                      <dd className="mt-1 text-sm text-gray-900">
                        {new Date(sessionData.created_at).toLocaleString()}
                      </dd>
                    </div>
                    <div className="sm:col-span-1">
                      <dt className="text-sm font-medium text-gray-500">Session ID</dt>
                      <dd className="mt-1 text-xs text-gray-500 font-mono">{sessionData.session_id}</dd>
                    </div>
                  </dl>
                </div>
              </div>

              {/* Tabs */}
              <div className="mb-6">
                <div className="sm:hidden">
                  <label htmlFor="tabs" className="sr-only">Select a tab</label>
                  <select
                    id="tabs"
                    name="tabs"
                    className="block w-full rounded-md border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                    value={activeTab}
                    onChange={(e) => setActiveTab(e.target.value as "transcript" | "soap")}
                  >
                    <option value="transcript">Transcript</option>
                    <option value="soap">SOAP Note</option>
                  </select>
                </div>
                <div className="hidden sm:block">
                  <div className="border-b border-gray-200">
                    <nav className="-mb-px flex space-x-8" aria-label="Tabs">
                      <button
                        onClick={() => setActiveTab("transcript")}
                        className={`${
                          activeTab === "transcript"
                            ? "border-blue-500 text-blue-600"
                            : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                        } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
                      >
                        Transcript
                      </button>
                      <button
                        onClick={() => setActiveTab("soap")}
                        className={`${
                          activeTab === "soap"
                            ? "border-blue-500 text-blue-600"
                            : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                        } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
                      >
                        SOAP Note
                        {soapNote && (
                          <span className="ml-2 bg-green-100 text-green-800 text-xs font-semibold px-2 py-0.5 rounded-full">
                            Available
                          </span>
                        )}
                      </button>
                    </nav>
                  </div>
                </div>
              </div>

              {activeTab === "transcript" && (
                <div className="bg-white shadow overflow-hidden sm:rounded-lg">
                  <div className="px-4 py-5 sm:px-6">
                    <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">Transcript</h3>
                    
                    {sessionData.transcripts.length === 0 ? (
                      <p className="text-gray-500 text-center py-8">No transcripts available for this session</p>
                    ) : (
                      <div className="space-y-4">
                        {sessionData.transcripts.map((transcript) => (
                          <div key={transcript.serial} className="bg-gray-50 p-4 rounded-md border border-gray-200">
                            {transcript.speaker && (
                              <div className="text-sm font-medium text-blue-600 mb-2">
                                {transcript.speaker}
                              </div>
                            )}
                            <p className="text-gray-800 text-base">{transcript.transcript}</p>
                            <div className="mt-2 text-xs text-gray-400 text-right">
                              {new Date(transcript.created_at).toLocaleString()}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {activeTab === "soap" && (
                <div className="bg-white shadow overflow-hidden sm:rounded-lg">
                  <div className="px-4 py-5 sm:px-6">
                    <div className="flex justify-between items-center mb-4">
                      <h3 className="text-lg leading-6 font-medium text-gray-900">SOAP Note</h3>
                      {!soapNote && !isGeneratingSoap && (
                        <button
                          onClick={generateSoapNote}
                          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                        >
                          Generate SOAP Note
                        </button>
                      )}
                      {soapNote && (
                        <div className="text-sm text-gray-500">
                          Generated: {new Date(soapNote.created_at).toLocaleString()}
                        </div>
                      )}
                    </div>
                    
                    {isSoapLoading || isGeneratingSoap ? (
                      <div className="flex justify-center items-center h-64">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                        <span className="ml-2 text-gray-600">
                          {isGeneratingSoap ? "Generating SOAP note..." : "Loading SOAP note..."}
                        </span>
                      </div>
                    ) : soapError ? (
                      <div className="bg-red-50 p-4 rounded-md border border-red-200">
                        <div className="flex">
                          <div className="flex-shrink-0">
                            <svg className="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                            </svg>
                          </div>
                          <div className="ml-3">
                            <div className="text-sm text-red-700">
                              <p>{soapError}</p>
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : !soapNote ? (
                      <div className="bg-yellow-50 p-4 rounded-md border border-yellow-200 text-center">
                        <p className="text-yellow-700">No SOAP note available for this session yet.</p>
                        <p className="text-sm text-yellow-600 mt-2">
                          Click the "Generate SOAP Note" button to create one based on the transcript.
                        </p>
                      </div>
                    ) : (
                      <div className="bg-gray-50 p-6 rounded-md border border-gray-200">
                        {renderFormattedSoapNote(soapNote.soap_text)}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}

          {!isLoading && (
            <div className="mt-4 flex justify-center">
              <button
                onClick={fetchSessionData}
                className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 mr-3"
              >
                Refresh Transcript
              </button>
              {soapNote && (
                <button
                  onClick={fetchSoapNote}
                  className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Refresh SOAP Note
                </button>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
} 
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="bg-white shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link href="/" className="flex-shrink-0 flex items-center">
              <h1 className="text-xl font-bold text-blue-600">Asha Transcription</h1>
            </Link>
          </div>
          
          <div className="flex items-center space-x-4">
            <Link
              href="/create"
              className={`px-3 py-2 rounded-md text-sm font-medium ${
                pathname === '/create'
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-700 hover:bg-gray-100 hover:text-blue-600'
              }`}
            >
              New Session
            </Link>
            <Link
              href="/sessions"
              className={`px-3 py-2 rounded-md text-sm font-medium ${
                pathname === '/sessions' || pathname.startsWith('/sessions/')
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-700 hover:bg-gray-100 hover:text-blue-600'
              }`}
            >
              Sessions
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
} 
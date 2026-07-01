import React from 'react';
import { Outlet } from 'react-router-dom';
import Nav from './components/Nav';

/**
 * App — top-level layout shell.
 *
 * The big animated background + Nav header live here so every route gets them
 * for free. The actual page content is rendered via <Outlet /> (defined in
 * main.jsx's <Routes>). Persona constants, voice-mode selectors, and page
 * bodies now live under /src/pages/*; this file is intentionally dumb.
 */
export default function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center py-12 px-4 relative overflow-hidden">
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-blue-600/20 blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-purple-600/20 blur-[120px] pointer-events-none"></div>

      <Nav />

      <main className="w-full max-w-3xl flex flex-col gap-6 relative z-10 items-center">
        <Outlet />
      </main>
    </div>
  );
}

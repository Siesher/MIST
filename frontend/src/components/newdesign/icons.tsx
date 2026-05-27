// MITS new_design — inline SVG icon set (ported verbatim from new_design/chat-app.jsx)
// Each icon is a ReactNode rendered inside the design-system className containers.

import type { ReactNode } from "react";

export const Icon: Record<string, ReactNode> = {
  chat: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M2 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H7l-3.5 2.5V12H4a2 2 0 0 1-2-2V4z" />
    </svg>
  ),
  list: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M5 3.5h9M5 8h9M5 12.5h9M2 3.5h1M2 8h1M2 12.5h1" />
    </svg>
  ),
  graph: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="4" cy="4" r="2" />
      <circle cx="12" cy="4" r="2" />
      <circle cx="8" cy="12" r="2" />
      <path d="M5.5 5.5 7 10.5M10.5 5.5 9 10.5M6 4h4" />
    </svg>
  ),
  chart: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M2 13V3M2 13h12" />
      <rect x="4" y="8" width="2.5" height="5" />
      <rect x="7.5" y="5" width="2.5" height="8" />
      <rect x="11" y="10" width="2.5" height="3" />
    </svg>
  ),
  database: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <ellipse cx="8" cy="3.5" rx="5" ry="1.8" />
      <path d="M3 3.5v9c0 1 2.2 1.8 5 1.8s5-.8 5-1.8v-9M3 8c0 1 2.2 1.8 5 1.8s5-.8 5-1.8" />
    </svg>
  ),
  user: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="8" cy="5.5" r="2.5" />
      <path d="M3 14a5 5 0 0 1 10 0" strokeLinecap="round" />
    </svg>
  ),
  signin: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.5 2H12a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9.5" />
      <path d="M3 8h7m-3-3 3 3-3 3" />
    </svg>
  ),
  plus: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <path d="M8 3v10M3 8h10" />
    </svg>
  ),
  send: (
    <svg viewBox="0 0 16 16" fill="currentColor">
      <path d="M2.3 1.6 14 7.5a.5.5 0 0 1 0 .9L2.3 14.3a.5.5 0 0 1-.7-.6l1.6-4.7a.5.5 0 0 1 .4-.3L9 8 3.7 6.3a.5.5 0 0 1-.4-.3L1.7 2.2a.5.5 0 0 1 .6-.6Z" />
    </svg>
  ),
  mic: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <rect x="6" y="2" width="4" height="8" rx="2" />
      <path d="M3.5 7.5a4.5 4.5 0 0 0 9 0M8 12v2" />
    </svg>
  ),
  image: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <rect x="2" y="2.5" width="12" height="11" rx="2" />
      <circle cx="6" cy="6.5" r="1.3" />
      <path d="m2.5 11.5 3.5-3 3 2.5 2-1.5 2.5 2" />
    </svg>
  ),
  github: (
    <svg viewBox="0 0 16 16" fill="currentColor">
      <path d="M8 0a8 8 0 0 0-2.5 15.6c.4.1.5-.2.5-.4v-1.5c-2 .4-2.5-.5-2.7-1 0-.1-.5-.9-.8-1.1-.3-.2-.7-.6 0-.6.6 0 1 .6 1.2.8.7 1.2 1.9 1 2.4.8 0-.5.3-1 .5-1.1-1.8-.2-3.6-.9-3.6-3.9 0-.9.3-1.6.8-2.2 0-.2-.4-1 .1-2.2 0 0 .7-.2 2.3.8a8 8 0 0 1 4 0c1.6-1 2.3-.8 2.3-.8.5 1.2.2 2 .1 2.2.5.6.8 1.3.8 2.2 0 3-1.9 3.7-3.6 3.9.3.2.5.7.5 1.4v2.1c0 .2.1.5.5.4A8 8 0 0 0 8 0Z" />
    </svg>
  ),
  sparkle: (
    <svg viewBox="0 0 16 16" fill="currentColor">
      <path d="M8 0 9.5 6.5 16 8 9.5 9.5 8 16 6.5 9.5 0 8 6.5 6.5z" />
    </svg>
  ),
  bookOpen: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M2 3v10l4-1 2 .5 2-.5 4 1V3l-4 1-2-.5L6 4 2 3Z" />
      <path d="M8 4v9" />
    </svg>
  ),
  settings: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="8" cy="8" r="2" />
      <path strokeLinecap="round" d="m13.5 9.5-.7-.5a5 5 0 0 0 0-2l.7-.5a1 1 0 0 0 .2-1.3l-1-1.6a1 1 0 0 0-1.2-.4l-.8.3a5 5 0 0 0-1.7-1l-.1-.9a1 1 0 0 0-1-.8H7a1 1 0 0 0-1 .8L5.9 3a5 5 0 0 0-1.7 1L3.5 4a1 1 0 0 0-1.2.3l-1 1.6a1 1 0 0 0 .2 1.3l.8.6a5 5 0 0 0 0 2l-.8.6a1 1 0 0 0-.2 1.3l1 1.6a1 1 0 0 0 1.2.4l.8-.3a5 5 0 0 0 1.7 1l.1.9a1 1 0 0 0 1 .8h2a1 1 0 0 0 1-.8l.1-.9a5 5 0 0 0 1.7-1l.8.3a1 1 0 0 0 1.2-.4l1-1.6a1 1 0 0 0-.2-1.3Z" />
    </svg>
  ),
  sun: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="8" cy="8" r="3" />
      <path strokeLinecap="round" d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.5 1.5M11.5 11.5 13 13M3 13l1.5-1.5M11.5 4.5 13 3" />
    </svg>
  ),
  moon: (
    <svg viewBox="0 0 16 16" fill="currentColor">
      <path d="M6.5 1a7 7 0 1 0 8.5 8.5A6 6 0 0 1 6.5 1Z" />
    </svg>
  ),
};

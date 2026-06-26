/// <reference types="vite/client" />

interface FrappeBootUser {
  name?: string;
  full_name?: string;
}

interface FrappeBoot {
  sitename?: string;
  user?: FrappeBootUser | string;
  [key: string]: unknown;
}

declare global {
  interface Window {
    csrf_token?: string;
    app_name?: string;
    frappe?: {
      boot?: FrappeBoot;
    };
  }
}

export {};

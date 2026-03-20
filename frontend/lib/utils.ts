import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

/**
 * API_BASE - Base URL for API calls.
 * Points to the backend /api prefix.
 * Used by Dashboard and other pages that call backend REST endpoints.
 */
export const API_BASE = `${BACKEND_URL}/api`;

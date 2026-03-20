/**
 * Next.js API Route: /api/chat
 * Proxy SSE stream từ FastAPI Backend về Frontend.
 * Mở luồng SSE kết nối với FastAPI.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Forward request to FastAPI backend
    const backendResponse = await fetch(`${BACKEND_URL}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: body.message,
        conversation_id: body.conversation_id || null,
        user_id: body.user_id || "default_user",
      }),
    });

    if (!backendResponse.ok) {
      return NextResponse.json(
        { error: `Backend error: ${backendResponse.status}` },
        { status: backendResponse.status }
      );
    }

    // Stream the SSE response back to the client
    const stream = backendResponse.body;
    if (!stream) {
      return NextResponse.json(
        { error: "No response stream from backend" },
        { status: 500 }
      );
    }

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (error: any) {
    console.error("Chat API route error:", error);
    return NextResponse.json(
      { error: error.message || "Internal server error" },
      { status: 500 }
    );
  }
}

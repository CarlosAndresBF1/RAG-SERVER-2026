import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";

const RAG_API_URL = process.env.RAG_API_URL || "http://localhost:8080";
const RAG_API_KEY = process.env.RAG_INTERNAL_KEY || "dev-key";

const headers = {
  "Content-Type": "application/json",
  ...(RAG_API_KEY ? { "X-API-Key": RAG_API_KEY } : {}),
};

export async function GET() {
  const res = await fetch(`${RAG_API_URL}/api/v1/tokens`, { headers });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function POST(req: NextRequest) {
  const session = await auth();
  const body = await req.json();

  // Inject the admin user ID from the session
  body.issued_by = session?.user?.id ?? body.issued_by ?? "00000000-0000-0000-0000-000000000000";

  const res = await fetch(`${RAG_API_URL}/api/v1/tokens`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

import { NextRequest, NextResponse } from "next/server";

const RAG_API_URL = process.env.RAG_API_URL || "http://localhost:8080";
const RAG_API_KEY = process.env.RAG_INTERNAL_KEY || "dev-key";

export async function POST(req: NextRequest) {
  const formData = await req.formData();

  const res = await fetch(`${RAG_API_URL}/api/v1/upload`, {
    method: "POST",
    headers: RAG_API_KEY ? { "X-API-Key": RAG_API_KEY } : {},
    body: formData,
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

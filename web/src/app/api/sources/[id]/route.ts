import { NextRequest, NextResponse } from "next/server";

const RAG_API_URL = process.env.RAG_API_URL || "http://localhost:8080";
const RAG_API_KEY = process.env.RAG_INTERNAL_KEY || "dev-key";

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  const res = await fetch(`${RAG_API_URL}/api/v1/sources/${id}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      ...(RAG_API_KEY ? { "X-API-Key": RAG_API_KEY } : {}),
    },
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

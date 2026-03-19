"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { Upload, FileText, CheckCircle2, XCircle, Loader2, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface FileEntry {
  file: File;
  status: "pending" | "uploading" | "queued" | "failed";
  sourceType?: string;
  jobId?: string;
  error?: string;
}

const ACCEPTED_TYPES: Record<string, string[]> = {
  "text/markdown": [".md"],
  "text/plain": [".txt", ".rst"],
  "application/xml": [".xml"],
  "application/json": [".json"],
  "application/pdf": [".pdf"],
  "application/x-httpd-php": [".php"],
  "application/msword": [".doc"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
};

function detectSourceType(name: string): string {
  if (/IPS_Annex_B/i.test(name)) return "annex_b_spec";
  if (/BIMPAY_(TECHNICAL|INFRASTRUCTURE)/i.test(name)) return "tech_doc";
  if (/\.php$/i.test(name)) return "php_code";
  if (/\.xml$/i.test(name)) return "xml_example";
  if (/\.postman_collection\.json$/i.test(name)) return "postman_collection";
  if (/\.docx?$/i.test(name)) return "word_doc";
  if (/annex[_\s]?[ac]/i.test(name)) return "odyssey_spec";
  if (/alias|qr|home.?banking/i.test(name)) return "odyssey_doc";
  return "generic_text";
}

export default function IngestPage() {
  const router = useRouter();
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [replaceExisting, setReplaceExisting] = useState(false);
  const [processing, setProcessing] = useState(false);

  const onDrop = useCallback((accepted: File[]) => {
    const entries: FileEntry[] = accepted.map((file) => ({
      file,
      status: "pending",
      sourceType: detectSourceType(file.name),
    }));
    setFiles((prev) => [...prev, ...entries]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: 50 * 1024 * 1024,
    disabled: processing,
  });

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const processAll = async () => {
    setProcessing(true);
    let allQueued = true;

    for (let i = 0; i < files.length; i++) {
      const entry = files[i];
      if (entry.status !== "pending") continue;

      // Upload file
      setFiles((prev) =>
        prev.map((f, idx) => (idx === i ? { ...f, status: "uploading" } : f))
      );

      try {
        const formData = new FormData();
        formData.append("file", entry.file);
        const uploadRes = await fetch("/api/upload", { method: "POST", body: formData });
        if (!uploadRes.ok) throw new Error(await uploadRes.text());
        const { path } = await uploadRes.json();

        // Queue ingest (fire-and-forget — returns immediately with job_id)
        const ingestRes = await fetch("/api/ingest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_path: path,
            source_type: entry.sourceType,
            replace_existing: replaceExisting,
          }),
        });
        if (!ingestRes.ok) throw new Error(await ingestRes.text());
        const result = await ingestRes.json();

        setFiles((prev) =>
          prev.map((f, idx) =>
            idx === i ? { ...f, status: "queued", jobId: result.job_id } : f
          )
        );
      } catch (err) {
        allQueued = false;
        setFiles((prev) =>
          prev.map((f, idx) =>
            idx === i ? { ...f, status: "failed", error: String(err) } : f
          )
        );
      }
    }

    setProcessing(false);

    // Redirect to jobs page after a short delay so user sees the queued status
    if (allQueued) {
      setTimeout(() => router.push("/jobs"), 1200);
    }
  };

  const pendingCount = files.filter((f) => f.status === "pending").length;
  const queuedCount = files.filter((f) => f.status === "queued").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-3xl font-serif text-primary tracking-tight">Ingest Sources</h2>
        <p className="text-muted-foreground text-sm">
          Upload documents into the knowledge base. Processing runs in the background — you can
          navigate away safely.
        </p>
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors ${
          isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
        } ${processing ? "opacity-50 pointer-events-none" : ""}`}
      >
        <input {...getInputProps()} />
        <Upload className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
        <p className="text-sm text-muted-foreground">
          {isDragActive
            ? "Drop files here…"
            : "Drag & drop files here, or click to browse"}
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          .md, .php, .xml, .json, .pdf, .txt, .rst, .doc, .docx — max 50 MB
        </p>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="border border-border/50 bg-card rounded-md shadow-sm">
          <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between">
            <h3 className="font-serif text-lg text-primary">Files ({files.length})</h3>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={replaceExisting}
                  onChange={(e) => setReplaceExisting(e.target.checked)}
                  disabled={processing}
                  className="rounded border-border"
                />
                Replace existing
              </label>
              {queuedCount > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => router.push("/jobs")}
                >
                  <ExternalLink className="h-4 w-4 mr-1" />
                  View Jobs
                </Button>
              )}
              <Button
                onClick={processAll}
                disabled={processing || pendingCount === 0}
                size="sm"
              >
                {processing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-1" />
                    Uploading…
                  </>
                ) : (
                  `Ingest ${pendingCount} file${pendingCount !== 1 ? "s" : ""}`
                )}
              </Button>
            </div>
          </div>
          <div className="divide-y divide-border/30">
            {files.map((entry, i) => (
              <div key={i} className="px-4 py-3 flex items-center gap-3">
                <StatusIcon status={entry.status} />
                <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{entry.file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {(entry.file.size / 1024).toFixed(1)} KB
                    {entry.status === "queued" && " · Queued for processing"}
                    {entry.error && ` · ${entry.error}`}
                  </p>
                </div>
                <Badge variant="outline">{entry.sourceType?.replace(/_/g, " ")}</Badge>
                {entry.status === "pending" && !processing && (
                  <button
                    onClick={() => removeFile(i)}
                    className="text-muted-foreground hover:text-destructive text-sm"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatusIcon({ status }: { status: FileEntry["status"] }) {
  switch (status) {
    case "queued":
      return <CheckCircle2 className="h-4 w-4 text-green-600 flex-shrink-0" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-destructive flex-shrink-0" />;
    case "uploading":
      return <Loader2 className="h-4 w-4 text-secondary animate-spin flex-shrink-0" />;
    default:
      return <div className="h-4 w-4 rounded-full border-2 border-border flex-shrink-0" />;
  }
}

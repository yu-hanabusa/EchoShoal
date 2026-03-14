import { useState, useRef } from "react";
import { uploadDocument } from "../api/client";
import type { ProcessResult } from "../api/types";

interface Props {
  onUploaded: () => void;
}

export default function DocumentUpload({ onUploaded }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("");
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setError("");
    setResult(null);

    try {
      const res = await uploadDocument(file, source || undefined);
      setResult(res);
      setFile(null);
      setSource("");
      if (inputRef.current) inputRef.current.value = "";
      onUploaded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{ marginBottom: "2rem" }}>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxWidth: "500px" }}>
        <div>
          <label style={{ display: "block", marginBottom: "0.25rem", fontWeight: 600 }}>
            File (.txt, .pdf)
          </label>
          <input
            ref={inputRef}
            type="file"
            accept=".txt,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </div>

        <div>
          <label style={{ display: "block", marginBottom: "0.25rem", fontWeight: 600 }}>
            Source (optional)
          </label>
          <input
            type="text"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="e.g. IPA IT人材白書2024"
            style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc" }}
          />
        </div>

        <button
          type="submit"
          disabled={!file || uploading}
          style={{
            padding: "0.75rem",
            borderRadius: "4px",
            border: "none",
            backgroundColor: uploading ? "#9ca3af" : "#3b82f6",
            color: "white",
            fontWeight: 600,
            cursor: uploading ? "wait" : "pointer",
          }}
        >
          {uploading ? "Uploading..." : "Upload & Analyze"}
        </button>
      </form>

      {error && (
        <div style={{ marginTop: "1rem", padding: "0.75rem", backgroundColor: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "4px", color: "#dc2626" }}>
          {error}
        </div>
      )}

      {result && (
        <div style={{ marginTop: "1rem", padding: "1rem", backgroundColor: "#f0fdf4", border: "1px solid #86efac", borderRadius: "4px" }}>
          <h4 style={{ margin: "0 0 0.5rem" }}>Extraction Result</h4>
          <p>Entities found: {result.entities_found}</p>
          {result.technologies.length > 0 && (
            <p>Technologies: {result.technologies.join(", ")}</p>
          )}
          {result.organizations.length > 0 && (
            <p>Organizations: {result.organizations.join(", ")}</p>
          )}
          {result.policies.length > 0 && (
            <p>Policies: {result.policies.join(", ")}</p>
          )}
          {result.new_nodes_created > 0 && (
            <p>New graph nodes created: {result.new_nodes_created}</p>
          )}
        </div>
      )}
    </div>
  );
}

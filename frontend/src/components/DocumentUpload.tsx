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
    <div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <label htmlFor="doc-file" className="block text-sm text-text-secondary mb-1.5">
              ファイル（.txt, .pdf）
            </label>
            <input
              ref={inputRef}
              id="doc-file"
              type="file"
              accept=".txt,.pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-text-primary file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-surface-2 file:text-text-secondary hover:file:bg-border file:cursor-pointer file:transition-colors"
            />
          </div>

          <div className="flex-1">
            <label htmlFor="doc-source" className="block text-sm text-text-secondary mb-1.5">
              ソース名<span className="text-text-tertiary ml-1">（任意）</span>
            </label>
            <input
              id="doc-source"
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="例: IPA IT人材白書2024"
              className="w-full rounded-md bg-surface-0 border border-border px-3 py-1.5 text-sm text-text-primary placeholder-text-tertiary focus:border-interactive focus:ring-1 focus:ring-interactive outline-none"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={!file || uploading}
          className="px-5 py-2 rounded-md bg-interactive hover:bg-interactive-hover disabled:bg-border-strong disabled:text-text-tertiary text-white text-sm font-medium transition-colors cursor-pointer disabled:cursor-not-allowed"
        >
          {uploading ? "解析中..." : "アップロード & 解析"}
        </button>
      </form>

      {error && (
        <div className="mt-4 px-4 py-3 rounded-md bg-negative-light border border-negative/20 text-negative text-sm" role="alert">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-4 px-4 py-3 rounded-md bg-positive-light border border-positive/20 text-sm">
          <p className="font-medium text-text-primary mb-1">
            抽出完了: {result.entities_found}件のエンティティ
          </p>
          <div className="space-y-0.5 text-text-secondary">
            {result.technologies.length > 0 && (
              <p>技術: {result.technologies.join(", ")}</p>
            )}
            {result.organizations.length > 0 && (
              <p>組織: {result.organizations.join(", ")}</p>
            )}
            {result.policies.length > 0 && (
              <p>政策: {result.policies.join(", ")}</p>
            )}
            {result.new_nodes_created > 0 && (
              <p className="text-positive font-medium">
                新規グラフノード: {result.new_nodes_created}件作成
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

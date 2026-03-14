import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getDocuments } from "../api/client";
import DocumentUpload from "../components/DocumentUpload";

export default function DocumentsPage() {
  const { data: documents, refetch, isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: getDocuments,
  });

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto", padding: "2rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2rem" }}>
        <h1 style={{ margin: 0 }}>Documents</h1>
        <Link to="/" style={{ color: "#3b82f6" }}>Back to Home</Link>
      </div>

      <section>
        <h2>Upload Document</h2>
        <p style={{ color: "#6b7280" }}>
          Upload IT industry reports, job data, or news articles (PDF/TXT).
          Entities will be extracted via NLP and stored in the knowledge graph.
        </p>
        <DocumentUpload onUploaded={() => refetch()} />
      </section>

      <section>
        <h2>Uploaded Documents</h2>
        {isLoading ? (
          <p>Loading...</p>
        ) : !documents || documents.length === 0 ? (
          <p style={{ color: "#9ca3af" }}>No documents uploaded yet.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left" }}>
                <th style={{ padding: "0.5rem" }}>Filename</th>
                <th style={{ padding: "0.5rem" }}>Source</th>
                <th style={{ padding: "0.5rem" }}>Size</th>
                <th style={{ padding: "0.5rem" }}>Entities</th>
                <th style={{ padding: "0.5rem" }}>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.doc_id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                  <td style={{ padding: "0.5rem", fontWeight: 500 }}>{doc.filename}</td>
                  <td style={{ padding: "0.5rem", color: "#6b7280" }}>{doc.source || "-"}</td>
                  <td style={{ padding: "0.5rem" }}>
                    {doc.text_length > 1000
                      ? `${(doc.text_length / 1000).toFixed(1)}K chars`
                      : `${doc.text_length} chars`}
                  </td>
                  <td style={{ padding: "0.5rem" }}>{doc.entity_count}</td>
                  <td style={{ padding: "0.5rem", color: "#9ca3af", fontSize: "0.875rem" }}>
                    {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString("ja-JP") : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

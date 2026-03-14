import { useQuery } from "@tanstack/react-query";
import { getDocuments } from "../api/client";
import DocumentUpload from "../components/DocumentUpload";

export default function DocumentsPage() {
  const { data: documents, refetch, isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: getDocuments,
  });

  return (
    <div className="min-h-screen bg-surface-1">
      <main className="max-w-4xl mx-auto px-4 py-8 space-y-8">
        {/* Upload Section */}
        <section className="rounded-md border border-border bg-surface-0 p-5">
          <h2 className="text-base font-medium text-text-primary mb-1">
            ドキュメントアップロード
          </h2>
          <p className="text-sm text-text-tertiary mb-4">
            IT業界レポート、求人データ、ニュース記事等（PDF/TXT）をアップロードすると、NLP解析で知識グラフにデータが蓄積されます。
          </p>
          <DocumentUpload onUploaded={() => refetch()} />
        </section>

        {/* Document List */}
        <section className="rounded-md border border-border bg-surface-0 p-5">
          <h2 className="text-base font-medium text-text-primary mb-4">
            アップロード済みドキュメント
          </h2>
          {isLoading ? (
            <p className="text-sm text-text-tertiary py-6 text-center">
              読み込み中...
            </p>
          ) : !documents || documents.length === 0 ? (
            <p className="text-sm text-text-tertiary py-6 text-center">
              まだドキュメントがありません
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-text-tertiary">
                    <th className="py-2 pr-3 font-medium">ファイル名</th>
                    <th className="py-2 px-3 font-medium">ソース</th>
                    <th className="py-2 px-3 font-medium text-right">サイズ</th>
                    <th className="py-2 px-3 font-medium text-right">エンティティ</th>
                    <th className="py-2 pl-3 font-medium text-right">アップロード日</th>
                  </tr>
                </thead>
                <tbody className="text-text-primary">
                  {documents.map((doc) => (
                    <tr
                      key={doc.doc_id}
                      className="border-b border-border last:border-b-0 hover:bg-surface-1 transition-colors"
                    >
                      <td className="py-2.5 pr-3 font-medium truncate max-w-[200px]">
                        {doc.filename}
                      </td>
                      <td className="py-2.5 px-3 text-text-secondary">
                        {doc.source || "\u2014"}
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums">
                        {doc.text_length > 1000
                          ? `${(doc.text_length / 1000).toFixed(1)}K`
                          : `${doc.text_length}`}
                        <span className="text-text-tertiary ml-0.5">文字</span>
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums">
                        {doc.entity_count}
                      </td>
                      <td className="py-2.5 pl-3 text-right text-text-tertiary text-xs">
                        {doc.uploaded_at
                          ? new Date(doc.uploaded_at).toLocaleDateString("ja-JP")
                          : "\u2014"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

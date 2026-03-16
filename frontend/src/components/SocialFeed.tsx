import { useState } from "react";
import type { SocialPost } from "../api/types";

interface Props {
  feed: SocialPost[];
}

const AGENT_COLORS = [
  "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
  "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
];

/** 投稿内容をクリーンアップ */
function cleanContent(raw: string): string {
  let s = raw;
  s = s.replace(/\(Impact:\s*[^)]*\)/gi, "");
  s = s.replace(/\{[^}]*\}/g, "");
  s = s.replace(/\\u([0-9a-fA-F]{4})/g, (_, hex: string) => String.fromCharCode(parseInt(hex, 16)));
  s = s.replace(/^(sign_up|refresh|login|logout|create_post|like|dislike|follow|unfollow|market_research|post_opinion|comment)\s*$/gm, "");
  s = s.replace(/\n{2,}/g, "\n").trim();
  return s;
}

function getAgentColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AGENT_COLORS[Math.abs(hash) % AGENT_COLORS.length];
}

export default function SocialFeed({ feed }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("");

  if (!feed || feed.length === 0) {
    return null;
  }

  const filteredFeed = filter
    ? feed.filter(
        (p) =>
          p.author.toLowerCase().includes(filter.toLowerCase()) ||
          p.content.toLowerCase().includes(filter.toLowerCase()),
      )
    : feed;

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="bg-surface-0 rounded-lg border border-border p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-text-primary">
          ステークホルダーの議論
        </h3>
        <span className="text-xs text-text-tertiary">
          {feed.length}件の投稿
        </span>
      </div>

      {/* Filter */}
      <input
        type="text"
        placeholder="投稿者名またはキーワードで検索..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="w-full mb-4 px-3 py-1.5 rounded-md border border-border bg-surface-1 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:ring-1 focus:ring-interactive"
      />

      {/* Posts */}
      <div className="space-y-3 max-h-[600px] overflow-y-auto">
        {filteredFeed.map((post) => {
          const color = getAgentColor(post.author);
          const isExpanded = expanded.has(post.id);
          const hasComments = post.comments && post.comments.length > 0;

          return (
            <div
              key={post.id}
              className="bg-surface-1 rounded-lg border border-border p-4"
            >
              {/* Post header */}
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0"
                  style={{ backgroundColor: color }}
                >
                  {post.author.charAt(0)}
                </span>
                <span className="text-sm font-medium text-text-primary">
                  {post.author}
                </span>
              </div>

              {/* Post content */}
              <p className="text-sm text-text-secondary mb-3 whitespace-pre-wrap">
                {cleanContent(post.content)}
              </p>

              {/* Engagement stats */}
              <div className="flex items-center gap-4 text-xs text-text-tertiary">
                {post.likes > 0 && (
                  <span title="いいね">+{post.likes}</span>
                )}
                {post.dislikes > 0 && (
                  <span title="低評価">-{post.dislikes}</span>
                )}
                {post.shares > 0 && (
                  <span title="シェア">{post.shares}件シェア</span>
                )}
                {hasComments && (
                  <button
                    onClick={() => toggleExpand(post.id)}
                    className="text-interactive hover:underline"
                  >
                    {isExpanded ? "閉じる" : `${post.comments.length}件のコメント`}
                  </button>
                )}
              </div>

              {/* Comments */}
              {isExpanded && hasComments && (
                <div className="mt-3 ml-4 border-l-2 border-border pl-3 space-y-2">
                  {post.comments.map((comment, i) => {
                    const commentColor = getAgentColor(comment.author);
                    return (
                      <div key={i} className="text-xs">
                        <div className="flex items-center gap-1.5 mb-0.5">
                          <span
                            className="w-4 h-4 rounded-full flex items-center justify-center text-white text-[9px] font-bold"
                            style={{ backgroundColor: commentColor }}
                          >
                            {comment.author.charAt(0)}
                          </span>
                          <span className="font-medium text-text-primary">
                            {comment.author}
                          </span>
                          {comment.likes > 0 && (
                            <span className="text-text-tertiary">
                              +{comment.likes}
                            </span>
                          )}
                        </div>
                        <p className="text-text-secondary ml-6">
                          {cleanContent(comment.content)}
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

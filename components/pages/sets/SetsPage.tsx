"use client";

import * as React from "react";
import { ArrowRight, ClipboardCopy, FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { listSets } from "@/lib/api/v2";

type SetRow = {
  setId: string;
  status: string;
  title?: string | null;
  questionCount: number;
  sourceFilename?: string | null;
};

type SetListResponse = {
  sets: SetRow[];
  limit: number;
  offset: number;
};

const statusFilters = [
  { key: "all", label: "전체" },
  { key: "ready", label: "완료" },
  { key: "needs_review", label: "검토필요" },
  { key: "error", label: "실패" },
] as const;

const statusLabelMap: Record<string, string> = {
  created: "생성됨",
  extracting: "추출중",
  ready: "완료",
  needs_review: "검토필요",
  error: "실패",
};

export function SetsPage() {
  const [statusFilter, setStatusFilter] = React.useState<(typeof statusFilters)[number]["key"]>("all");
  const [rows, setRows] = React.useState<SetRow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const data = (await listSets({
          limit: 100,
          offset: 0,
          status: statusFilter,
        })) as SetListResponse;
        if (!cancelled) setRows(data.sets ?? []);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "세트 목록을 불러오지 못했습니다.");
          setRows([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [statusFilter]);

  return (
    <div className="container mx-auto px-4 min-h-screen bg-background">
      <header>
        <div className="flex h-16 items-center">
          <Link href="/" className="flex items-center space-x-2">
            <span className="font-mono text-sm text-muted-foreground hover:text-foreground transition-colors">
              ← 홈으로
            </span>
          </Link>
        </div>
      </header>

      <main className="flex flex-col items-center py-24">
        <h1 className="font-mono text-3xl font-bold sm:text-4xl md:text-5xl mb-4">
          문제 세트
        </h1>
        <p className="font-mono text-muted-foreground text-lg mb-12">
          생성된 문제 세트를 관리하거나 공유할 수 있습니다.
        </p>

        <div className="w-full max-w-2xl flex flex-wrap gap-2 mb-6">
          {statusFilters.map((filter) => (
            <button
              key={filter.key}
              onClick={() => setStatusFilter(filter.key)}
              className={`px-3 py-1.5 rounded-full text-xs font-mono border transition-colors cursor-pointer ${
                statusFilter === filter.key
                  ? "bg-[#FF6B2C] text-white border-[#FF6B2C]"
                  : "bg-background hover:bg-muted"
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>

        <div className="w-full max-w-2xl flex flex-col gap-4">
          {loading && (
            <div className="border-2 p-6 flex items-center gap-2 text-muted-foreground font-mono text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              세트 목록 로딩 중...
            </div>
          )}

          {error && !loading && (
            <div className="border-2 p-6 text-destructive font-mono text-sm">{error}</div>
          )}

          {!loading && !error && rows.length === 0 && (
            <div className="border-2 p-6 text-muted-foreground font-mono text-sm">
              조건에 맞는 세트가 없습니다.
            </div>
          )}

          {rows.map((set) => (
            <div
              key={set.setId}
              className="border-2 p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
            >
              <div className="flex items-start gap-4">
                <div className="rounded-full bg-[#FF6B2C]/10 p-3 shrink-0">
                  <FileText className="h-6 w-6 text-[#FF6B2C]" />
                </div>
                <div>
                  <h3 className="font-mono font-bold text-lg">{set.title || set.sourceFilename || set.setId}</h3>
                  <p className="font-mono text-sm text-muted-foreground mt-1">
                    문제 {set.questionCount}개 · 상태: {statusLabelMap[set.status] ?? set.status}
                  </p>
                </div>
              </div>

              <div className="flex gap-2 sm:shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigator.clipboard.writeText(set.setId)}
                  className="cursor-pointer rounded-none font-mono"
                >
                  <ClipboardCopy className="mr-1.5 h-4 w-4" />
                  ID 복사
                </Button>
                <Button
                  asChild
                  size="sm"
                  className="cursor-pointer rounded-none bg-[#FF6B2C] hover:bg-[#FF6B2C]/90 font-mono"
                >
                  <Link href={`/sets/${set.setId}`}>
                    세트 열기
                    <ArrowRight className="ml-1.5 h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

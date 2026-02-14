"use client";

import * as React from "react";
import {
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  FileText,
  FileUp,
  Loader2,
  Trash2,
  Upload,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createDocument, deleteSet, listSets } from "@/lib/api/v2";

type SetSummary = {
  setId: string;
  status: string;
  title?: string | null;
  questionCount: number;
  sourceFilename?: string | null;
};

type SetListResponse = {
  sets: SetSummary[];
  limit: number;
  offset: number;
};

const statusConfig = {
  ready: { icon: CheckCircle2, className: "bg-green-100 text-green-700", label: "완료" },
  extracting: { icon: Loader2, className: "bg-yellow-100 text-yellow-700", label: "추출중" },
  error: { icon: XCircle, className: "bg-red-100 text-red-700", label: "실패" },
  needs_review: { icon: XCircle, className: "bg-orange-100 text-orange-700", label: "검토필요" },
  created: { icon: Loader2, className: "bg-slate-100 text-slate-700", label: "생성됨" },
};

const ACCEPTED = ".pdf,.png,.jpg,.jpeg";
const MAX_SIZE = 20 * 1024 * 1024; // 20MB

export function DashboardPage() {
  const router = useRouter();
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const [file, setFile] = React.useState<File | null>(null);
  const [uploading, setUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [deletingSetId, setDeletingSetId] = React.useState<string | null>(null);
  const [mySets, setMySets] = React.useState<SetSummary[]>([]);

  const fetchRecentSets = React.useCallback(async () => {
    const data = (await listSets({ limit: 200, offset: 0 })) as SetListResponse;
    setMySets(data.sets || []);
  }, []);

  React.useEffect(() => {
    fetchRecentSets().catch(() => {
      // Keep dashboard usable even if set list fails.
    });
  }, [fetchRecentSets]);

  const handleFileChange = (picked: File | undefined) => {
    setError(null);
    if (!picked) return;
    if (picked.size > MAX_SIZE) {
      setError("파일 크기가 20MB를 초과합니다.");
      return;
    }
    setFile(picked);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    handleFileChange(e.dataTransfer.files[0]);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);

    try {
      const data = await createDocument(file);
      try {
        window.localStorage.setItem(`sedu:job:${data.setId}`, data.jobId);
      } catch {
        // Ignore storage errors in private mode.
      }
      fetchRecentSets().catch(() => {
        // no-op
      });
      router.push(`/sets/${data.setId}?jobId=${data.jobId}`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "알 수 없는 오류가 발생했습니다.",
      );
      setUploading(false);
    }
  };

  const handleDeleteSet = async (set: SetSummary) => {
    const label = set.title || set.sourceFilename || set.setId;
    const confirmed = window.confirm(`'${label}' 문제세트를 삭제할까요? 이 작업은 되돌릴 수 없습니다.`);
    if (!confirmed) return;

    setDeletingSetId(set.setId);
    setError(null);
    try {
      await deleteSet(set.setId);
      setMySets((prev) => prev.filter((item) => item.setId !== set.setId));
      try {
        window.localStorage.removeItem(`sedu:job:${set.setId}`);
      } catch {
        // no-op
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "문제세트 삭제에 실패했습니다.");
    } finally {
      setDeletingSetId(null);
    }
  };

  return (
    <div className="container mx-auto px-4 min-h-screen bg-background">
      <header>
        <div className="flex h-16 items-center justify-between">
          <Link href="/" className="flex items-center space-x-2">
            <span className="font-mono text-sm text-muted-foreground hover:text-foreground transition-colors">
              ← 홈으로
            </span>
          </Link>
        </div>
      </header>

      <main className="py-12">
        <h1 className="font-mono text-3xl font-bold sm:text-4xl mb-12">
          대시보드
        </h1>

        <div className="grid lg:grid-cols-2 gap-8 max-w-5xl">
          {/* Upload Card */}
          <section className="border-2 p-8">
            <h2 className="font-mono text-xl font-bold mb-2">시험지 업로드</h2>
            <p className="font-mono text-sm text-muted-foreground mb-6">
              PDF 또는 이미지를 업로드하면 문제를 자동 추출합니다.
            </p>

            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED}
              className="hidden"
              onChange={(e) => handleFileChange(e.target.files?.[0])}
            />

            {/* Drop zone */}
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              className="border-2 border-dashed rounded-lg p-10 flex flex-col items-center gap-4 hover:border-[#FF6B2C]/50 transition-colors cursor-pointer mb-6"
            >
              <div className="rounded-full bg-[#FF6B2C]/10 p-4">
                <Upload className="h-8 w-8 text-[#FF6B2C]" />
              </div>
              <p className="font-mono font-medium text-center">
                파일을 드래그하거나 클릭해서 업로드
              </p>
              <p className="font-mono text-sm text-muted-foreground">
                PDF, PNG, JPG (최대 20MB)
              </p>
              <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-muted">
                <FileUp className="h-4 w-4 text-muted-foreground" />
                <span className="font-mono text-sm text-muted-foreground">
                  {file ? file.name : "아직 선택된 파일이 없습니다"}
                </span>
              </div>
            </div>

            {/* Error */}
            {error && (
              <p className="font-mono text-sm text-destructive mb-4">
                {error}
              </p>
            )}

            {/* Upload button */}
            <Button
              size="lg"
              disabled={!file || uploading}
              onClick={handleUpload}
              className="cursor-pointer rounded-none w-full bg-[#FF6B2C] hover:bg-[#FF6B2C]/90 font-mono text-base py-6 disabled:opacity-50"
            >
              {uploading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  업로드 중...
                </>
              ) : (
                <>
                  업로드하고 문제세트 만들기
                  <ArrowRight className="ml-2 w-4 h-4" />
                </>
              )}
            </Button>
          </section>

          {/* My Sets */}
          <section className="border-2 p-8 flex flex-col min-h-[620px]">
            <h2 className="font-mono text-xl font-bold mb-2">내 문제세트</h2>
            <p className="font-mono text-sm text-muted-foreground mb-6">
              생성된 문제세트를 확인하고 관리할 수 있습니다.
            </p>

            <div className="flex flex-col gap-3 overflow-y-auto pr-1 max-h-[500px]">
              {mySets.map((set) => {
                const config = statusConfig[set.status as keyof typeof statusConfig] || {
                  icon: FileText,
                  className: "bg-slate-100 text-slate-700",
                  label: set.status,
                };
                const StatusIcon = config.icon;

                return (
                  <div
                    key={set.setId}
                    className="border p-4 flex items-center justify-between gap-4"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="rounded-full bg-[#FF6B2C]/10 p-2 shrink-0">
                        <FileText className="h-5 w-5 text-[#FF6B2C]" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-mono font-medium text-sm truncate">
                          {set.title || set.sourceFilename || set.setId}
                        </p>
                        <span
                          className={`inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded-full text-xs font-mono ${config.className}`}
                        >
                          <StatusIcon className="h-3 w-3" />
                          {config.label}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <Button
                        asChild
                        variant="outline"
                        size="sm"
                        className="cursor-pointer rounded-none font-mono shrink-0"
                      >
                        <Link href={`/sets/${set.setId}`}>
                          열기
                          <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                        </Link>
                      </Button>
                      <Button
                        variant="destructive"
                        size="icon-sm"
                        className="cursor-pointer rounded-none shrink-0"
                        disabled={deletingSetId === set.setId}
                        onClick={() => {
                          handleDeleteSet(set).catch(() => {
                            // handled in state
                          });
                        }}
                        aria-label="문제세트 삭제"
                      >
                        {deletingSetId === set.setId ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                );
              })}
              {mySets.length === 0 && (
                <div className="border p-4 font-mono text-sm text-muted-foreground">
                  표시할 세트가 없습니다.
                </div>
              )}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

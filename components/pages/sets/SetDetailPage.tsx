"use client";

import * as React from "react";
import {
  BookOpen,
  ChevronRight,
  Clock3,
  FileText,
  Image as ImageIcon,
  Loader2,
  Sparkles,
  Tag,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { SolvePanel } from "@/components/pages/sets/solve/SolvePanel";
import { API_BASE } from "@/lib/api/client";
import {
  createQuestionVariant,
  getJob,
  getJobEvents,
  getQuestion,
  getSet,
  listQuestionVariants,
  listQuestionsForSet,
  reprocessQuestion,
  type JobDetailResponse,
  type JobEventItem,
  type QuestionDetailResponse,
  type QuestionListResponse,
  type QuestionSummary,
  type SetDetailResponse,
  type VariantItem,
} from "@/lib/api/v2";

const tabs = [
  { id: "questions", label: "문제", icon: FileText },
  { id: "variants", label: "변형", icon: Sparkles },
  { id: "solve", label: "풀기", icon: BookOpen },
] as const;

type TabId = (typeof tabs)[number]["id"];
type ViewQuestionSummary = QuestionSummary & { croppedImageUrl?: string | null };
type ViewQuestionDetail = QuestionDetailResponse & { croppedImageUrl?: string | null };

const statusLabelMap: Record<string, string> = {
  created: "생성됨",
  extracting: "추출중",
  ready: "완료",
  needs_review: "검토필요",
  error: "실패",
};

const statusClassMap: Record<string, string> = {
  created: "bg-slate-100 text-slate-700",
  extracting: "bg-yellow-100 text-yellow-800",
  ready: "bg-green-100 text-green-800",
  needs_review: "bg-orange-100 text-orange-800",
  error: "bg-red-100 text-red-800",
};

function formatStatus(status: string) {
  return statusLabelMap[status] ?? status;
}

function statusClass(status: string) {
  return statusClassMap[status] ?? "bg-muted text-muted-foreground";
}

const jobStatusClassMap: Record<string, string> = {
  queued: "bg-slate-100 text-slate-700",
  running: "bg-blue-100 text-blue-700",
  done: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

const stageClassMap: Record<string, string> = {
  queued: "bg-slate-100 text-slate-700",
  preprocess: "bg-amber-100 text-amber-700",
  layout: "bg-indigo-100 text-indigo-700",
  ocr: "bg-cyan-100 text-cyan-700",
  split: "bg-teal-100 text-teal-700",
  completed: "bg-green-100 text-green-700",
  error: "bg-red-100 text-red-700",
};

function jobStatusClass(status: string) {
  return jobStatusClassMap[status] ?? "bg-muted text-muted-foreground";
}

function stageClass(stage: string | null | undefined) {
  if (!stage) return "bg-muted text-muted-foreground";
  return stageClassMap[stage] ?? "bg-muted text-muted-foreground";
}

function getUnit(metadata: Record<string, unknown> | null | undefined): string {
  if (!metadata) return "-";
  const unitPath = metadata["unitPath"];
  if (Array.isArray(unitPath)) {
    return unitPath.map((v) => String(v)).join(" > ");
  }
  const unit = metadata["unit"];
  if (typeof unit === "string" && unit.trim()) return unit;
  return "-";
}

function getDifficulty(metadata: Record<string, unknown> | null | undefined): string {
  if (!metadata) return "-";
  const difficulty = metadata["difficulty"];
  if (typeof difficulty === "string" && difficulty.trim()) return difficulty;
  return "-";
}

function questionTitle(q: { numberLabel?: string | null; orderIndex: number } | null): string {
  if (!q) return "문제";
  return q.numberLabel ? `문제 ${q.numberLabel}` : `문제 ${q.orderIndex}`;
}

function resolveApiUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_BASE}${path}`;
}

function formatEventTime(value: string): string {
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleTimeString("ko-KR", { hour12: false });
}

function JobTimelineCard({
  jobId,
  job,
  events,
  error,
}: {
  jobId: string | null;
  job: JobDetailResponse | null;
  events: JobEventItem[];
  error: string | null;
}) {
  if (!jobId) {
    return null;
  }

  return (
    <section className="mb-8 border-2 p-4 sm:p-5 bg-muted/20">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <Clock3 className="h-4 w-4" />
        <h2 className="font-mono text-sm font-bold">추출 작업 타임라인</h2>
        <span className="font-mono text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
          {jobId}
        </span>
      </div>

      {error && <p className="font-mono text-xs text-destructive mb-2">{error}</p>}

      {job ? (
        <div className="mb-3 flex flex-wrap gap-2 font-mono text-xs">
          <span className={`px-2 py-1 rounded ${jobStatusClass(job.status)}`}>{job.status}</span>
          <span className={`px-2 py-1 rounded ${stageClass(job.stage)}`}>stage: {job.stage ?? "-"}</span>
          <span className="px-2 py-1 rounded bg-muted">progress: {Math.round(job.percent)}%</span>
        </div>
      ) : (
        <p className="font-mono text-xs text-muted-foreground mb-3">Job 상태를 확인하는 중...</p>
      )}

      <div className="border rounded-sm bg-background">
        {events.length === 0 ? (
          <p className="font-mono text-xs text-muted-foreground px-3 py-2">이벤트가 아직 없습니다.</p>
        ) : (
          <ul className="divide-y">
            {events.slice(-8).reverse().map((event, index) => (
              <li
                key={`${event.createdAt}-${index}`}
                className="grid grid-cols-[72px_88px_1fr_64px] gap-2 px-3 py-2 font-mono text-xs"
              >
                <span className="text-muted-foreground">{formatEventTime(event.createdAt)}</span>
                <span className={`inline-flex items-center px-2 py-0.5 rounded ${jobStatusClass(event.status)}`}>
                  {event.status}
                </span>
                <span className={`truncate inline-flex items-center px-2 py-0.5 rounded ${stageClass(event.stage)}`}>
                  {event.stage ?? "-"}
                </span>
                <span className="text-right">{Math.round(event.percent)}%</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function QuestionsTab({
  questions,
  selectedQId,
  onSelect,
  selectedDetail,
  onReprocess,
  reprocessing,
}: {
  questions: ViewQuestionSummary[];
  selectedQId: string | null;
  onSelect: (id: string) => void;
  selectedDetail: ViewQuestionDetail | null;
  onReprocess: () => Promise<void>;
  reprocessing: boolean;
}) {
  const unit = getUnit(selectedDetail?.metadata);
  const difficulty = getDifficulty(selectedDetail?.metadata);
  const imageUrl = resolveApiUrl(selectedDetail?.croppedImageUrl);

  return (
    <div className="grid md:grid-cols-[280px_1fr] gap-6">
      <div className="border-2 divide-y">
        {questions.length === 0 && (
          <div className="px-4 py-6 font-mono text-sm text-muted-foreground">
            문제를 추출 중입니다.
          </div>
        )}
        {questions.map((item) => {
          const selected = item.questionId === selectedQId;
          return (
            <button
              key={item.questionId}
              onClick={() => onSelect(item.questionId)}
              className={`w-full text-left px-4 py-3 font-mono text-sm flex items-center justify-between transition-colors cursor-pointer ${
                selected
                  ? "bg-[#FF6B2C]/10 text-[#FF6B2C] font-bold"
                  : "hover:bg-muted"
              }`}
            >
              <span className="truncate">{questionTitle(item)}</span>
              <ChevronRight className="h-4 w-4 shrink-0" />
            </button>
          );
        })}
      </div>

      <div className="border-2 p-6 flex flex-col gap-6">
        <div className="flex items-center justify-between gap-4">
          <h3 className="font-mono text-xl font-bold">{questionTitle(selectedDetail)}</h3>
          <Button
            variant="outline"
            size="sm"
            disabled={!selectedDetail || reprocessing}
            onClick={() => {
              onReprocess().catch(() => {
                // handled by page-level error state
              });
            }}
            className="font-mono rounded-none cursor-pointer"
          >
            {reprocessing ? (
              <>
                <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                재처리 중
              </>
            ) : (
              "문항 재처리"
            )}
          </Button>
        </div>

        <p className="font-mono leading-relaxed whitespace-pre-wrap">
          {selectedDetail?.ocrText?.trim() || "OCR 결과가 아직 없습니다."}
        </p>

        {imageUrl ? (
          <div className="border-2 rounded-lg p-2 bg-white">
            <img
              src={imageUrl}
              alt={`${questionTitle(selectedDetail)} crop`}
              className="w-full h-auto rounded"
            />
          </div>
        ) : (
          <div className="border-2 border-dashed rounded-lg p-8 flex flex-col items-center gap-2 text-muted-foreground">
            <ImageIcon className="h-10 w-10" />
            <span className="font-mono text-sm">CROP 이미지가 아직 없습니다</span>
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-muted font-mono text-xs">
            <Tag className="h-3 w-3" />
            단원: {unit}
          </span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-muted font-mono text-xs">
            난이도: {difficulty}
          </span>
        </div>
      </div>
    </div>
  );
}

function VariantsTab({
  selectedDetail,
  variants,
  loading,
  error,
  onGenerate,
}: {
  selectedDetail: ViewQuestionDetail | null;
  variants: VariantItem[];
  loading: boolean;
  error: string | null;
  onGenerate: () => Promise<void>;
}) {
  const first = variants[0];
  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div className="border-2 p-6">
        <p className="font-mono text-xs text-muted-foreground mb-2">원본 문제</p>
        <h3 className="font-mono font-bold mb-2">{questionTitle(selectedDetail)}</h3>
        <p className="font-mono text-sm leading-relaxed whitespace-pre-wrap">
          {selectedDetail?.ocrText?.trim() || "OCR 결과가 아직 없습니다."}
        </p>
      </div>

      <Button
        size="lg"
        disabled={!selectedDetail || loading}
        onClick={() => {
          onGenerate().catch(() => {
            // handled by page-level error display
          });
        }}
        className="cursor-pointer rounded-none self-start bg-[#FF6B2C] hover:bg-[#FF6B2C]/90 font-mono text-base px-8 py-6"
      >
        {loading ? (
          <>
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            생성 중...
          </>
        ) : (
          <>
            <Sparkles className="mr-2 h-5 w-5" />
            변형문제 생성
          </>
        )}
      </Button>

      <div className="border-2 border-dashed p-6 flex flex-col gap-4">
        <p className="font-mono text-xs text-muted-foreground">생성된 변형문제</p>
        {error && <p className="font-mono text-sm text-destructive">{error}</p>}

        <div className="rounded bg-muted p-4">
          <p className="font-mono text-sm whitespace-pre-wrap">
            {first?.body || "변형문제가 여기에 표시됩니다"}
          </p>
        </div>

        <p className="font-mono text-xs text-muted-foreground mt-2">정답</p>
        <div className="rounded bg-muted p-3">
          <span className="font-mono text-sm text-muted-foreground">
            {first?.answer || "—"}
          </span>
        </div>

        <p className="font-mono text-xs text-muted-foreground mt-2">해설</p>
        <div className="rounded bg-muted p-3">
          <span className="font-mono text-sm text-muted-foreground whitespace-pre-wrap">
            {first?.explanation || "—"}
          </span>
        </div>
      </div>
    </div>
  );
}

export function SetDetailPage({ setId }: { setId: string }) {
  const searchParams = useSearchParams();
  const queryJobId = searchParams.get("jobId");

  const [activeTab, setActiveTab] = React.useState<TabId>("questions");
  const [setInfo, setSetInfo] = React.useState<SetDetailResponse | null>(null);
  const [questions, setQuestions] = React.useState<ViewQuestionSummary[]>([]);
  const [selectedQId, setSelectedQId] = React.useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = React.useState<ViewQuestionDetail | null>(null);
  const [variantRows, setVariantRows] = React.useState<VariantItem[]>([]);
  const [variantLoading, setVariantLoading] = React.useState(false);
  const [variantError, setVariantError] = React.useState<string | null>(null);
  const [reprocessing, setReprocessing] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [jobId, setJobId] = React.useState<string | null>(null);
  const [jobInfo, setJobInfo] = React.useState<JobDetailResponse | null>(null);
  const [jobEvents, setJobEvents] = React.useState<JobEventItem[]>([]);
  const [jobError, setJobError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (queryJobId) {
      setJobId(queryJobId);
      try {
        window.localStorage.setItem(`sedu:job:${setId}`, queryJobId);
      } catch {
        // Ignore private mode storage errors.
      }
      return;
    }

    try {
      const stored = window.localStorage.getItem(`sedu:job:${setId}`);
      if (stored) setJobId(stored);
    } catch {
      // no-op
    }
  }, [queryJobId, setId]);

  const fetchSetAndQuestions = React.useCallback(async () => {
    const [setData, listData] = await Promise.all([
      getSet(setId),
      listQuestionsForSet(setId) as Promise<QuestionListResponse>,
    ]);

    setSetInfo(setData);
    setQuestions((listData.questions || []) as ViewQuestionSummary[]);
    if (!jobId && setData.latestJobId) {
      setJobId(setData.latestJobId);
      try {
        window.localStorage.setItem(`sedu:job:${setId}`, setData.latestJobId);
      } catch {
        // no-op
      }
    }

    setSelectedQId((prev) => {
      const items = listData.questions || [];
      if (items.length === 0) return null;
      if (!prev) return items[0].questionId;
      return items.some((q) => q.questionId === prev) ? prev : items[0].questionId;
    });
  }, [setId, jobId]);

  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        setError(null);
        await fetchSetAndQuestions();
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "데이터를 불러오지 못했습니다.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [fetchSetAndQuestions]);

  React.useEffect(() => {
    if (!setInfo || !["created", "extracting"].includes(setInfo.status)) return;

    const timer = window.setInterval(() => {
      fetchSetAndQuestions().catch(() => {
        // keep previous UI state on transient polling failure
      });
    }, 2000);

    return () => window.clearInterval(timer);
  }, [setInfo, fetchSetAndQuestions]);

  const fetchJobTimeline = React.useCallback(async () => {
    if (!jobId) return;
    const [job, events] = await Promise.all([getJob(jobId), getJobEvents(jobId)]);
    setJobInfo(job);
    setJobEvents(events.events || []);
  }, [jobId]);

  React.useEffect(() => {
    if (!jobId) {
      setJobInfo(null);
      setJobEvents([]);
      setJobError(null);
      return;
    }

    let cancelled = false;

    const run = async () => {
      try {
        await fetchJobTimeline();
        if (!cancelled) setJobError(null);
      } catch (e) {
        if (!cancelled) {
          setJobError(e instanceof Error ? e.message : "Job 상태 조회 실패");
        }
      }
    };

    run().catch(() => {
      // handled in run
    });

    const shouldPoll =
      !jobInfo ||
      ["queued", "running"].includes(jobInfo.status) ||
      ["created", "extracting"].includes(setInfo?.status ?? "");

    if (!shouldPoll) return;

    const timer = window.setInterval(() => {
      run().catch(() => {
        // no-op
      });
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [jobId, fetchJobTimeline, jobInfo, setInfo]);

  React.useEffect(() => {
    if (!selectedQId) {
      setSelectedDetail(null);
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        const data = (await getQuestion(selectedQId)) as ViewQuestionDetail;
        if (!cancelled) setSelectedDetail(data);
      } catch {
        if (!cancelled) setSelectedDetail(null);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedQId]);

  const fetchVariants = React.useCallback(async (questionId: string) => {
    const data = await listQuestionVariants(questionId);
    setVariantRows(data.variants || []);
  }, []);

  React.useEffect(() => {
    if (!selectedQId) {
      setVariantRows([]);
      return;
    }
    fetchVariants(selectedQId).catch(() => {
      setVariantRows([]);
    });
  }, [selectedQId, fetchVariants]);

  const generateVariant = React.useCallback(async () => {
    if (!selectedQId) return;
    setVariantLoading(true);
    setVariantError(null);
    try {
      await createQuestionVariant(selectedQId, { variantType: "paraphrase" });
      await fetchVariants(selectedQId);
    } catch (e) {
      setVariantError(e instanceof Error ? e.message : "변형문제 생성 실패");
    } finally {
      setVariantLoading(false);
    }
  }, [selectedQId, fetchVariants]);

  const reprocessCurrentQuestion = React.useCallback(async () => {
    if (!selectedQId) return;
    setReprocessing(true);
    setError(null);
    try {
      await reprocessQuestion(selectedQId);
      await fetchSetAndQuestions();
      const detail = (await getQuestion(selectedQId)) as ViewQuestionDetail;
      setSelectedDetail(detail);
    } catch (e) {
      setError(e instanceof Error ? e.message : "문항 재처리에 실패했습니다.");
    } finally {
      setReprocessing(false);
    }
  }, [selectedQId, fetchSetAndQuestions]);

  const solveQuestion = React.useMemo(() => {
    return {
      questionId: selectedDetail?.questionId ?? "",
      setId: selectedDetail?.setId ?? setId,
      id: selectedDetail?.orderIndex ?? 1,
      title: questionTitle(selectedDetail),
      text: selectedDetail?.ocrText?.trim() || "문제 텍스트를 불러오는 중입니다.",
      unit: getUnit(selectedDetail?.metadata),
      difficulty: getDifficulty(selectedDetail?.metadata),
      imageUrl: resolveApiUrl(selectedDetail?.croppedImageUrl),
    };
  }, [selectedDetail, setId]);

  return (
    <div className="container mx-auto px-4 min-h-screen bg-background">
      <header>
        <div className="flex h-16 items-center gap-4">
          <Link href="/dashboard" className="flex items-center space-x-2">
            <span className="font-mono text-sm text-muted-foreground hover:text-foreground transition-colors">
              ← 대시보드
            </span>
          </Link>
        </div>
      </header>

      <main className="py-12">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-6">
          <h1 className="font-mono text-3xl font-bold sm:text-4xl">문제세트</h1>
          <span className="font-mono text-sm text-muted-foreground px-3 py-1 rounded-full bg-muted">
            {setId}
          </span>
          {setInfo && (
            <span
              className={`font-mono text-xs px-2.5 py-1 rounded-full ${statusClass(setInfo.status)}`}
            >
              {formatStatus(setInfo.status)} · {setInfo.questionCount}문항
            </span>
          )}
          {setInfo?.status === "extracting" && (
            <span className="inline-flex items-center gap-2 font-mono text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              추출 진행 중 (2초 간격 자동 새로고침)
            </span>
          )}
        </div>

        <JobTimelineCard jobId={jobId} job={jobInfo} events={jobEvents} error={jobError} />

        {error && (
          <p className="font-mono text-sm text-destructive mb-6">{error}</p>
        )}

        {loading ? (
          <div className="font-mono text-sm text-muted-foreground">불러오는 중...</div>
        ) : (
          <>
            <div className="flex border-b-2 mb-8">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center gap-2 px-6 py-3 font-mono text-sm font-medium transition-colors cursor-pointer -mb-[2px] ${
                      activeTab === tab.id
                        ? "border-b-2 border-[#FF6B2C] text-[#FF6B2C]"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {activeTab === "questions" && (
              <QuestionsTab
                questions={questions}
                selectedQId={selectedQId}
                onSelect={setSelectedQId}
                selectedDetail={selectedDetail}
                onReprocess={reprocessCurrentQuestion}
                reprocessing={reprocessing}
              />
            )}
            {activeTab === "variants" && (
              <VariantsTab
                selectedDetail={selectedDetail}
                variants={variantRows}
                loading={variantLoading}
                error={variantError}
                onGenerate={generateVariant}
              />
            )}
            {activeTab === "solve" && <SolvePanel key={selectedQId ?? "empty"} question={solveQuestion} />}
          </>
        )}
      </main>
    </div>
  );
}

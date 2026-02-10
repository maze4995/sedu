"use client";

import * as React from "react";
import {
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  FileText,
  FileUp,
  Loader2,
  Upload,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useRouter } from "next/navigation";

const placeholderSets = [
  { id: "set-1", title: "통합과학 1단원 모의고사", status: "완료" as const },
  { id: "set-2", title: "통합과학 에너지 단원", status: "추출중" as const },
  { id: "set-3", title: "2025 3월 모의고사", status: "실패" as const },
];

const statusConfig = {
  완료: { icon: CheckCircle2, className: "bg-green-100 text-green-700" },
  추출중: { icon: Loader2, className: "bg-yellow-100 text-yellow-700" },
  실패: { icon: XCircle, className: "bg-red-100 text-red-700" },
};

const ACCEPTED = ".pdf,.png,.jpg,.jpeg";
const MAX_SIZE = 20 * 1024 * 1024; // 20MB

export function DashboardPage() {
  const router = useRouter();
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const [file, setFile] = React.useState<File | null>(null);
  const [uploading, setUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

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
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("http://localhost:8000/uploads", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error(`서버 오류 (${res.status})`);

      const data = await res.json();
      router.push(`/sets/${data.setId}`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "업로드에 실패했습니다. 서버 연결을 확인해주세요.",
      );
      setUploading(false);
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
          <section className="border-2 p-8">
            <h2 className="font-mono text-xl font-bold mb-2">내 문제세트</h2>
            <p className="font-mono text-sm text-muted-foreground mb-6">
              생성된 문제세트를 확인하고 관리할 수 있습니다.
            </p>

            <div className="flex flex-col gap-3">
              {placeholderSets.map((set) => {
                const config = statusConfig[set.status];
                const StatusIcon = config.icon;

                return (
                  <div
                    key={set.id}
                    className="border p-4 flex items-center justify-between gap-4"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="rounded-full bg-[#FF6B2C]/10 p-2 shrink-0">
                        <FileText className="h-5 w-5 text-[#FF6B2C]" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-mono font-medium text-sm truncate">
                          {set.title}
                        </p>
                        <span
                          className={`inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded-full text-xs font-mono ${config.className}`}
                        >
                          <StatusIcon className="h-3 w-3" />
                          {set.status}
                        </span>
                      </div>
                    </div>

                    <Button
                      asChild
                      variant="outline"
                      size="sm"
                      className="cursor-pointer rounded-none font-mono shrink-0"
                    >
                      <Link href={`/sets/${set.id}`}>
                        열기
                        <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                      </Link>
                    </Button>
                  </div>
                );
              })}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

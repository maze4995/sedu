"use client";

import { ArrowRight, FileUp, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export function UploadPage() {
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
          시험지 업로드
        </h1>
        <p className="font-mono text-muted-foreground text-lg mb-12">
          PDF 또는 이미지를 업로드하면 문제를 자동으로 추출합니다.
        </p>

        <div className="w-full max-w-xl border-2 border-dashed rounded-lg p-12 flex flex-col items-center gap-6 hover:border-[#FF6B2C]/50 transition-colors cursor-pointer">
          <div className="rounded-full bg-[#FF6B2C]/10 p-6">
            <Upload className="h-10 w-10 text-[#FF6B2C]" />
          </div>
          <div className="text-center">
            <p className="font-mono font-medium text-lg">
              파일을 드래그하거나 클릭해서 업로드
            </p>
            <p className="font-mono text-sm text-muted-foreground mt-2">
              PDF, PNG, JPG (최대 20MB)
            </p>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-muted">
            <FileUp className="h-4 w-4 text-muted-foreground" />
            <span className="font-mono text-sm text-muted-foreground">
              아직 선택된 파일이 없습니다
            </span>
          </div>
        </div>

        <Button
          size="lg"
          className="cursor-pointer rounded-none mt-12 bg-[#FF6B2C] hover:bg-[#FF6B2C]/90 font-mono text-base px-8 py-6"
        >
          문제 추출 시작
          <ArrowRight className="ml-2 w-4 h-4" />
        </Button>
      </main>
    </div>
  );
}

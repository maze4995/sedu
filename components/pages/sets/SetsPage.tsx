"use client";

import { ArrowRight, ClipboardCopy, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

const placeholderSets = [
  { id: 1, title: "통합과학 연습 세트", count: 10, code: "SCI-2841" },
  { id: 2, title: "통합과학 연습 세트", count: 10, code: "SCI-2841" },
  { id: 3, title: "통합과학 연습 세트", count: 10, code: "SCI-2841" },
];

export function SetsPage() {
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

        <div className="w-full max-w-2xl flex flex-col gap-4">
          {placeholderSets.map((set) => (
            <div
              key={set.id}
              className="border-2 p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
            >
              <div className="flex items-start gap-4">
                <div className="rounded-full bg-[#FF6B2C]/10 p-3 shrink-0">
                  <FileText className="h-6 w-6 text-[#FF6B2C]" />
                </div>
                <div>
                  <h3 className="font-mono font-bold text-lg">{set.title}</h3>
                  <p className="font-mono text-sm text-muted-foreground mt-1">
                    문제 {set.count}개 · 코드: {set.code}
                  </p>
                </div>
              </div>

              <div className="flex gap-2 sm:shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  className="cursor-pointer rounded-none font-mono"
                >
                  <ClipboardCopy className="mr-1.5 h-4 w-4" />
                  코드 복사
                </Button>
                <Button
                  asChild
                  size="sm"
                  className="cursor-pointer rounded-none bg-[#FF6B2C] hover:bg-[#FF6B2C]/90 font-mono"
                >
                  <Link href="/solve/demo">
                    문제 풀기
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

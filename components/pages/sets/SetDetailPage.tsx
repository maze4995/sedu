"use client";

import * as React from "react";
import {
  ArrowRight,
  BookOpen,
  ChevronRight,
  FileText,
  Image as ImageIcon,
  Lightbulb,
  Sparkles,
  Tag,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

/* ------------------------------------------------------------------ */
/*  Placeholder data                                                   */
/* ------------------------------------------------------------------ */

const questions = [
  {
    id: 1,
    title: "문제 1",
    text: "다음 중 물질의 상태 변화에 대한 설명으로 옳은 것은?",
    unit: "물질과 규칙성",
    difficulty: "중",
  },
  {
    id: 2,
    title: "문제 2",
    text: "그림은 지구 시스템의 에너지 흐름을 나타낸 것이다. A와 B에 해당하는 에너지원을 서술하시오.",
    unit: "시스템과 상호작용",
    difficulty: "상",
  },
  {
    id: 3,
    title: "문제 3",
    text: "산화·환원 반응의 예로 적절한 것을 <보기>에서 모두 고르시오.",
    unit: "변화와 다양성",
    difficulty: "중",
  },
  {
    id: 4,
    title: "문제 4",
    text: "생태계에서 물질의 순환과 에너지 흐름의 차이점을 설명하시오.",
    unit: "환경과 에너지",
    difficulty: "하",
  },
  {
    id: 5,
    title: "문제 5",
    text: "그래프는 시간에 따른 방사성 원소의 붕괴 곡선이다. 반감기를 구하시오.",
    unit: "물질과 규칙성",
    difficulty: "상",
  },
];

const tabs = [
  { id: "questions", label: "문제", icon: FileText },
  { id: "variants", label: "변형", icon: Sparkles },
  { id: "solve", label: "풀기", icon: BookOpen },
] as const;

type TabId = (typeof tabs)[number]["id"];

/* ------------------------------------------------------------------ */
/*  Tab: 문제                                                          */
/* ------------------------------------------------------------------ */

function QuestionsTab({
  selected,
  onSelect,
}: {
  selected: number;
  onSelect: (id: number) => void;
}) {
  const q = questions.find((q) => q.id === selected) ?? questions[0];

  return (
    <div className="grid md:grid-cols-[280px_1fr] gap-6">
      {/* Left list */}
      <div className="border-2 divide-y">
        {questions.map((item) => (
          <button
            key={item.id}
            onClick={() => onSelect(item.id)}
            className={`w-full text-left px-4 py-3 font-mono text-sm flex items-center justify-between transition-colors cursor-pointer ${
              item.id === selected
                ? "bg-[#FF6B2C]/10 text-[#FF6B2C] font-bold"
                : "hover:bg-muted"
            }`}
          >
            {item.title}
            <ChevronRight className="h-4 w-4 shrink-0" />
          </button>
        ))}
      </div>

      {/* Right detail */}
      <div className="border-2 p-6 flex flex-col gap-6">
        <h3 className="font-mono text-xl font-bold">{q.title}</h3>

        <p className="font-mono leading-relaxed">{q.text}</p>

        {/* Image placeholder */}
        <div className="border-2 border-dashed rounded-lg p-8 flex flex-col items-center gap-2 text-muted-foreground">
          <ImageIcon className="h-10 w-10" />
          <span className="font-mono text-sm">이미지 영역</span>
        </div>

        {/* Metadata */}
        <div className="flex flex-wrap gap-3">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-muted font-mono text-xs">
            <Tag className="h-3 w-3" />
            단원: {q.unit}
          </span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-muted font-mono text-xs">
            난이도: {q.difficulty}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Tab: 변형                                                          */
/* ------------------------------------------------------------------ */

function VariantsTab({ selected }: { selected: number }) {
  const q = questions.find((q) => q.id === selected) ?? questions[0];

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      {/* Original question */}
      <div className="border-2 p-6">
        <p className="font-mono text-xs text-muted-foreground mb-2">원본 문제</p>
        <h3 className="font-mono font-bold mb-2">{q.title}</h3>
        <p className="font-mono text-sm leading-relaxed">{q.text}</p>
      </div>

      <Button
        size="lg"
        className="cursor-pointer rounded-none self-start bg-[#FF6B2C] hover:bg-[#FF6B2C]/90 font-mono text-base px-8 py-6"
      >
        <Sparkles className="mr-2 h-5 w-5" />
        변형문제 생성
      </Button>

      {/* Generated variant placeholder */}
      <div className="border-2 border-dashed p-6 flex flex-col gap-4">
        <p className="font-mono text-xs text-muted-foreground">생성된 변형문제</p>
        <div className="h-16 rounded bg-muted flex items-center justify-center">
          <span className="font-mono text-sm text-muted-foreground">
            변형문제가 여기에 표시됩니다
          </span>
        </div>

        <p className="font-mono text-xs text-muted-foreground mt-2">정답</p>
        <div className="h-10 rounded bg-muted flex items-center justify-center">
          <span className="font-mono text-sm text-muted-foreground">—</span>
        </div>

        <p className="font-mono text-xs text-muted-foreground mt-2">해설</p>
        <div className="h-20 rounded bg-muted flex items-center justify-center">
          <span className="font-mono text-sm text-muted-foreground">—</span>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Tab: 풀기                                                          */
/* ------------------------------------------------------------------ */

function SolveTab({ selected }: { selected: number }) {
  const q = questions.find((q) => q.id === selected) ?? questions[0];

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      {/* Question */}
      <div className="border-2 p-6">
        <h3 className="font-mono font-bold mb-3">{q.title}</h3>
        <p className="font-mono leading-relaxed">{q.text}</p>
      </div>

      {/* Answer input */}
      <div className="border-2 p-6 flex flex-col gap-4">
        <p className="font-mono text-sm font-bold">답안 입력</p>
        <textarea
          placeholder="답안을 입력하세요..."
          rows={3}
          className="w-full border-2 rounded-none px-4 py-3 font-mono text-sm placeholder:text-muted-foreground focus:outline-none focus:border-[#FF6B2C] transition-colors resize-none"
        />
        <Button
          size="lg"
          className="cursor-pointer rounded-none self-start bg-[#FF6B2C] hover:bg-[#FF6B2C]/90 font-mono text-base px-8 py-6"
        >
          제출하기
          <ArrowRight className="ml-2 w-4 h-4" />
        </Button>
      </div>

      {/* Hints */}
      <div className="border-2 p-6 flex flex-col gap-4">
        <p className="font-mono text-sm font-bold">AI 힌트</p>
        <div className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            className="cursor-pointer rounded-none font-mono"
          >
            <Lightbulb className="mr-1.5 h-4 w-4" />
            힌트 1 (약한 힌트)
          </Button>
          <Button
            variant="outline"
            className="cursor-pointer rounded-none font-mono"
          >
            <Lightbulb className="mr-1.5 h-4 w-4" />
            힌트 2 (강한 힌트)
          </Button>
        </div>
        <div className="h-20 rounded bg-muted flex items-center justify-center">
          <span className="font-mono text-sm text-muted-foreground">
            힌트를 요청하면 여기에 표시됩니다
          </span>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */

export function SetDetailPage({ setId }: { setId: string }) {
  const [activeTab, setActiveTab] = React.useState<TabId>("questions");
  const [selectedQ, setSelectedQ] = React.useState(1);

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
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-8">
          <h1 className="font-mono text-3xl font-bold sm:text-4xl">문제세트</h1>
          <span className="font-mono text-sm text-muted-foreground px-3 py-1 rounded-full bg-muted">
            {setId}
          </span>
        </div>

        {/* Tabs */}
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

        {/* Tab content */}
        {activeTab === "questions" && (
          <QuestionsTab selected={selectedQ} onSelect={setSelectedQ} />
        )}
        {activeTab === "variants" && <VariantsTab selected={selectedQ} />}
        {activeTab === "solve" && <SolveTab selected={selectedQ} />}
      </main>
    </div>
  );
}

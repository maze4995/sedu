"use client";

import * as React from "react";
import {
  ArrowRight,
  BrainCircuit,
  CirclePlay,
  FileSearch,
  GraduationCap,
  Lightbulb,
  MessageCircleQuestion,
  Sparkles,
} from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import Link from "next/link";

const highlights = [
  { icon: FileSearch, label: "문제 자동 추출" },
  { icon: Sparkles, label: "AI 변형문제" },
  { icon: Lightbulb, label: "AI  튜터" },
];

const features = [
  {
    icon: FileSearch,
    label: "문제 자동 추출",
    description: "PDF/이미지에서 문항을 자동 분리하고 메타데이터를 생성합니다.",
  },
  {
    icon: Sparkles,
    label: "AI 변형문제 생성",
    description: "교육과정 범위 내에서 변형문제·정답·해설을 생성합니다.",
  },
  {
    icon: MessageCircleQuestion,
    label: "AI 튜터 힌트",
    description: "풀이 흐름에 따라 약한 힌트→강한 힌트를 제공합니다.",
  },
];

export function MynaHero() {
  const ref = React.useRef(null);

  return (
    <div className="container mx-auto px-4 min-h-screen bg-background">
      <header>
        <div className="flex h-16 items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex items-center space-x-2">
              <BrainCircuit className="h-8 w-8 text-[#FF6B2C]" />
              <span className="font-mono text-xl font-bold">SEDU</span>
            </div>
          </Link>

          <nav className="hidden md:flex items-center space-x-8">
            <a href="#features" className="text-sm font-mono text-foreground hover:text-[#FF6B2C] transition-colors">
              기능 소개
            </a>
            <Link href="/dashboard" className="text-sm font-mono text-foreground hover:text-[#FF6B2C] transition-colors">
              대시보드
            </Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="container py-24">
          <div className="flex flex-col items-center text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="flex items-center gap-2 mb-6 px-4 py-2 rounded-full bg-[#FF6B2C]/10"
            >
              <GraduationCap className="h-5 w-5 text-[#FF6B2C]" />
              <span className="text-sm font-mono text-[#FF6B2C]">고등학교 통합과학</span>
            </motion.div>

            <motion.h1
              initial={{ filter: "blur(10px)", opacity: 0, y: 50 }}
              animate={{ filter: "blur(0px)", opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="relative font-mono text-4xl font-bold sm:text-5xl md:text-6xl lg:text-7xl max-w-4xl mx-auto leading-tight"
            >
              AI 통합과학 학습 도우미
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.8, duration: 0.6 }}
              className="mx-auto mt-8 max-w-2xl text-lg md:text-xl text-muted-foreground font-mono leading-relaxed whitespace-pre-line"
            >
              {"시험지를 업로드하면 문제를 자동 추출하고,\n변형문제와 단계별 힌트로 바로 학습할 수 있어요."}
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                delay: 1.2,
                duration: 0.6,
                type: "spring",
                stiffness: 100,
                damping: 10,
              }}
              className="mt-12 flex flex-col sm:flex-row gap-4"
            >
              <Button
                asChild
                size="lg"
                className="cursor-pointer rounded-none bg-[#FF6B2C] hover:bg-[#FF6B2C]/90 font-mono text-base px-8 py-6"
              >
                <Link href="/dashboard">
                  대시보드에서 시작하기
                  <ArrowRight className="ml-2 w-4 h-4" />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="cursor-pointer rounded-none font-mono text-base px-8 py-6 border-2"
              >
                <Link href="/sets/demo">
                  <CirclePlay className="mr-2 h-5 w-5" />
                  샘플 세트 보기
                </Link>
              </Button>
            </motion.div>

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1.8, duration: 0.6 }}
              className="mt-10 flex flex-wrap justify-center gap-6"
            >
              {highlights.map((item, index) => (
                <motion.div
                  key={item.label}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{
                    delay: 1.8 + index * 0.15,
                    duration: 0.6,
                    type: "spring",
                    stiffness: 100,
                    damping: 10,
                  }}
                  className="flex items-center gap-2 px-4"
                >
                  <item.icon className="h-4 w-4 text-[#FF6B2C]" />
                  <span className="text-sm font-mono text-muted-foreground">{item.label}</span>
                </motion.div>
              ))}
            </motion.div>
          </div>
        </section>

        <section id="features" className="container pb-24" ref={ref}>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 2.2, duration: 0.6 }}
            className="grid md:grid-cols-3 max-w-6xl mx-auto"
          >
            {features.map((feature, index) => (
              <motion.div
                key={feature.label}
                initial={{ opacity: 0, y: 50 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  delay: 2.2 + index * 0.2,
                  duration: 0.6,
                  type: "spring",
                  stiffness: 100,
                  damping: 10,
                }}
                className="flex flex-col items-center text-center p-8 bg-background border"
              >
                <div className="mb-6 rounded-full bg-[#FF6B2C]/10 p-4">
                  <feature.icon className="h-8 w-8 text-[#FF6B2C]" />
                </div>
                <h3 className="mb-4 text-xl font-mono font-bold">
                  {feature.label}
                </h3>
                <p className="text-muted-foreground font-mono text-sm leading-relaxed">
                  {feature.description}
                </p>
              </motion.div>
            ))}
          </motion.div>
        </section>
      </main>
    </div>
  );
}

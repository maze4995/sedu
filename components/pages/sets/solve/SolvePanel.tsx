"use client";

import * as React from "react";
import {
  Circle,
  Eraser,
  Image as ImageIcon,
  Pen,
  Plus,
  Send,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { requestQuestionHint } from "@/lib/api/v2";

/* ------------------------------------------------------------------ */
/*  Types & Constants                                                   */
/* ------------------------------------------------------------------ */

type CanvasMode = "draw" | "erase";

const THICKNESS = [
  { label: "얇게", value: 2 },
  { label: "보통", value: 4 },
  { label: "두껍게", value: 8 },
] as const;

const COLORS = [
  { label: "검정", value: "#222" },
  { label: "파랑", value: "#2563EB" },
  { label: "빨강", value: "#DC2626" },
] as const;

interface ChatMsg {
  role: "ai" | "user";
  text: string;
}

export interface SolvePanelQuestion {
  questionId: string;
  setId: string;
  id: number;
  title: string;
  text: string;
  unit: string;
  difficulty: string;
  imageUrl?: string | null;
}

/* ------------------------------------------------------------------ */
/*  CanvasOverlay                                                       */
/* ------------------------------------------------------------------ */

interface CanvasOverlayHandle {
  clear: () => void;
}

const CanvasOverlay = React.forwardRef<
  CanvasOverlayHandle,
  { mode: CanvasMode; strokeWidth: number; strokeColor: string }
>(function CanvasOverlay({ mode, strokeWidth, strokeColor }, ref) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const drawing = React.useRef(false);

  /* Keep refs in sync so pointer handlers never see stale values */
  const modeRef = React.useRef(mode);
  const widthRef = React.useRef(strokeWidth);
  const colorRef = React.useRef(strokeColor);
  React.useEffect(() => {
    modeRef.current = mode;
  }, [mode]);
  React.useEffect(() => {
    widthRef.current = strokeWidth;
  }, [strokeWidth]);
  React.useEffect(() => {
    colorRef.current = strokeColor;
  }, [strokeColor]);

  /* Resize canvas pixel buffer to match parent layout size */
  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;

    const sync = () => {
      const w = parent.clientWidth;
      const h = parent.clientHeight;
      if (canvas.width === w && canvas.height === h) return;
      const data = canvas.toDataURL();
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        const img = new window.Image();
        img.onload = () => ctx.drawImage(img, 0, 0);
        img.src = data;
      }
    };

    const observer = new ResizeObserver(() => sync());
    observer.observe(parent);
    sync();
    return () => observer.disconnect();
  }, []);

  React.useImperativeHandle(ref, () => ({
    clear: () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      ctx?.clearRect(0, 0, canvas.width, canvas.height);
    },
  }));

  const pos = (e: React.PointerEvent) => {
    const r = canvasRef.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };

  /* Only draw with pen / mouse — let touch pass through for scrolling */
  const isDrawInput = (e: React.PointerEvent) =>
    e.pointerType === "pen" || e.pointerType === "mouse";

  const onPointerDown = (e: React.PointerEvent) => {
    if (!isDrawInput(e)) return;
    e.preventDefault();
    drawing.current = true;
    const ctx = canvasRef.current?.getContext("2d");
    if (!ctx) return;
    const p = pos(e);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drawing.current) return;
    if (!isDrawInput(e)) return;
    e.preventDefault();
    const ctx = canvasRef.current?.getContext("2d");
    if (!ctx) return;
    const p = pos(e);
    if (modeRef.current === "erase") {
      ctx.globalCompositeOperation = "destination-out";
      ctx.lineWidth = widthRef.current * 4;
    } else {
      ctx.globalCompositeOperation = "source-over";
      ctx.lineWidth = widthRef.current;
      ctx.strokeStyle = colorRef.current;
    }
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
  };

  const onPointerUp = (e: React.PointerEvent) => {
    if (!isDrawInput(e)) return;
    drawing.current = false;
    const ctx = canvasRef.current?.getContext("2d");
    if (ctx) ctx.globalCompositeOperation = "source-over";
  };

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full z-10"
      style={{
        touchAction: "pan-y",
        cursor: mode === "erase" ? "cell" : "crosshair",
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerLeave={onPointerUp}
    />
  );
});

/* ------------------------------------------------------------------ */
/*  SolvePanel                                                          */
/* ------------------------------------------------------------------ */

export function SolvePanel({ question }: { question: SolvePanelQuestion }) {
  const problemCanvasRef = React.useRef<CanvasOverlayHandle>(null);
  const scratchCanvasRef = React.useRef<CanvasOverlayHandle>(null);
  const chatEndRef = React.useRef<HTMLDivElement>(null);

  const [penWidth, setPenWidth] = React.useState<number>(THICKNESS[1].value);
  const [penColor, setPenColor] = React.useState<string>(COLORS[0].value);
  const [canvasMode, setCanvasMode] = React.useState<CanvasMode>("draw");
  const [scratchHeight, setScratchHeight] = React.useState(1000);

  const [messages, setMessages] = React.useState<ChatMsg[]>([
    {
      role: "ai",
      text: `안녕하세요! "${question.title}" 문제를 함께 풀어볼까요? 문제 위에 직접 풀이를 작성하면 피드백을 드릴게요.`,
    },
  ]);
  const [input, setInput] = React.useState("");
  const [sending, setSending] = React.useState(false);

  React.useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const clearAll = () => {
    problemCanvasRef.current?.clear();
    scratchCanvasRef.current?.clear();
  };

  const send = async () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    if (!question.questionId) {
      setMessages((prev) => [...prev, { role: "user", text: trimmed }, { role: "ai", text: "문항이 선택되지 않았습니다." }]);
      setInput("");
      return;
    }
    setSending(true);
    const nextMessages = [...messages, { role: "user" as const, text: trimmed }];
    setMessages(nextMessages);
    setInput("");

    try {
      const data = await requestQuestionHint(question.questionId, {
        level: "weak",
        recentChat: nextMessages.map((m) => ({ role: m.role, text: m.text })),
        strokeSummary: "",
      });
      setMessages((prev) => [...prev, { role: "ai", text: data.hint || "힌트를 생성하지 못했습니다." }]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "힌트 생성에 실패했습니다.";
      setMessages((prev) => [...prev, { role: "ai", text: msg }]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="grid md:grid-cols-[7fr_3fr] gap-0 border-2 h-[calc(100vh-280px)] min-h-[500px] overflow-hidden">
      {/* ---- Left: Workspace ---- */}
      <div className="flex flex-col border-r-2 min-h-0">
        {/* Header */}
        <div className="border-b-2 px-5 py-3 shrink-0">
          <h3 className="font-mono font-bold text-sm">{question.title}</h3>
          <p className="font-mono text-sm text-muted-foreground mt-1 leading-relaxed line-clamp-2">
            {question.text}
          </p>
        </div>

        {/* Toolbar */}
        <div className="border-b px-3 py-2 flex flex-wrap items-center gap-2 shrink-0 bg-muted/30">
          {/* Mode: draw / erase */}
          <div className="flex rounded border overflow-hidden">
            <button
              onClick={() => setCanvasMode("draw")}
              className={`inline-flex items-center gap-1.5 px-3 min-h-[44px] font-mono text-xs transition-colors cursor-pointer ${
                canvasMode === "draw"
                  ? "bg-[#FF6B2C] text-white"
                  : "hover:bg-muted"
              }`}
            >
              <Pen className="h-3.5 w-3.5" />
              펜
            </button>
            <button
              onClick={() => setCanvasMode("erase")}
              className={`inline-flex items-center gap-1.5 px-3 min-h-[44px] font-mono text-xs transition-colors cursor-pointer ${
                canvasMode === "erase"
                  ? "bg-[#FF6B2C] text-white"
                  : "hover:bg-muted"
              }`}
            >
              <Eraser className="h-3.5 w-3.5" />
              지우개
            </button>
          </div>

          <div className="w-px h-6 bg-border" />

          {/* Thickness */}
          <div className="flex rounded border overflow-hidden">
            {THICKNESS.map((t) => (
              <button
                key={t.value}
                onClick={() => setPenWidth(t.value)}
                className={`inline-flex items-center gap-1.5 px-3 min-h-[44px] font-mono text-xs transition-colors cursor-pointer ${
                  penWidth === t.value
                    ? "bg-foreground text-background"
                    : "hover:bg-muted"
                }`}
              >
                <Circle
                  className="shrink-0"
                  style={{ width: t.value + 6, height: t.value + 6 }}
                  fill="currentColor"
                />
                {t.label}
              </button>
            ))}
          </div>

          <div className="w-px h-6 bg-border" />

          {/* Color */}
          <div className="flex rounded border overflow-hidden">
            {COLORS.map((c) => (
              <button
                key={c.value}
                onClick={() => setPenColor(c.value)}
                className={`inline-flex items-center gap-1.5 px-3 min-h-[44px] font-mono text-xs transition-colors cursor-pointer ${
                  penColor === c.value ? "bg-muted font-bold" : "hover:bg-muted"
                }`}
              >
                <span
                  className="inline-block w-3.5 h-3.5 rounded-full border"
                  style={{ backgroundColor: c.value }}
                />
                {c.label}
              </button>
            ))}
          </div>

          <div className="ml-auto" />
          <button
            onClick={clearAll}
            className="inline-flex items-center gap-1.5 px-3 min-h-[44px] rounded font-mono text-xs text-destructive hover:bg-destructive/10 transition-colors cursor-pointer"
          >
            <Trash2 className="h-3.5 w-3.5" />
            전체 삭제
          </button>
        </div>

        {/* Scrollable workspace */}
        <div className="flex-1 overflow-y-auto bg-white min-h-0">
          {/* Problem area */}
          <div className="relative">
            <div className="p-6 flex flex-col gap-4">
              {question.imageUrl ? (
                <div className="border-2 rounded-lg p-2 bg-white">
                  <img src={question.imageUrl} alt={`${question.title} problem`} className="w-full h-auto rounded" />
                </div>
              ) : (
                <div className="border-2 border-dashed rounded-lg p-10 flex flex-col items-center gap-2 text-muted-foreground">
                  <ImageIcon className="h-10 w-10" />
                  <span className="font-mono text-sm">문제 이미지 영역</span>
                </div>
              )}
              {/* Problem text */}
              <p className="font-mono text-sm leading-relaxed">
                {question.text}
              </p>
            </div>
            <CanvasOverlay
              ref={problemCanvasRef}
              mode={canvasMode}
              strokeWidth={penWidth}
              strokeColor={penColor}
            />
          </div>

          {/* Divider */}
          <div className="border-t-2 border-dashed px-5 py-2 bg-muted/20">
            <span className="font-mono text-xs text-muted-foreground">
              풀이 여백
            </span>
          </div>

          {/* Scratch area */}
          <div className="relative" style={{ minHeight: scratchHeight }}>
            <CanvasOverlay
              ref={scratchCanvasRef}
              mode={canvasMode}
              strokeWidth={penWidth}
              strokeColor={penColor}
            />
          </div>

          {/* Add more space */}
          <div className="border-t border-dashed px-5 py-3 flex justify-center">
            <button
              onClick={() => setScratchHeight((h) => h + 600)}
              className="inline-flex items-center gap-1.5 px-4 min-h-[44px] rounded border-2 border-dashed font-mono text-xs text-muted-foreground hover:text-foreground hover:border-foreground transition-colors cursor-pointer"
            >
              <Plus className="h-4 w-4" />
              여백 추가
            </button>
          </div>
        </div>
      </div>

      {/* ---- Right: AI Tutor Chat ---- */}
      <div className="flex flex-col min-h-0">
        {/* Chat header */}
        <div className="border-b-2 px-5 py-4 shrink-0 flex items-center gap-2">
          <span className="inline-flex items-center justify-center h-7 w-7 rounded-full bg-[#FF6B2C] text-white text-xs font-bold">
            AI
          </span>
          <span className="font-mono font-bold text-sm">AI 튜터</span>
          <span className="font-mono text-xs text-muted-foreground ml-auto">
            AI 힌트 (베타)
          </span>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3 min-h-0">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] px-4 py-3 font-mono text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === "ai"
                    ? "bg-muted rounded-tr-xl rounded-br-xl rounded-bl-xl"
                    : "bg-[#FF6B2C] text-white rounded-tl-xl rounded-bl-xl rounded-br-xl"
                }`}
              >
                {msg.text}
              </div>
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className="border-t-2 px-4 py-3 shrink-0 flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="질문을 입력하세요... (Shift+Enter 줄바꿈)"
            rows={1}
            className="flex-1 border-2 rounded-none px-4 py-2.5 font-mono text-sm placeholder:text-muted-foreground focus:outline-none focus:border-[#FF6B2C] transition-colors resize-none min-h-[44px] max-h-[120px] overflow-y-auto"
          />
          <Button
            onClick={send}
            disabled={sending}
            className="cursor-pointer rounded-none bg-[#FF6B2C] hover:bg-[#FF6B2C]/90 px-4 min-h-[44px]"
          >
            {sending ? <span className="font-mono text-xs">...</span> : <Send className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
}

import { apiGet, apiPost } from "@/lib/api/client";
import type { QuestionDetailResponse } from "@/lib/api/v2/types";

export async function getQuestion(questionId: string): Promise<QuestionDetailResponse> {
  return apiGet<QuestionDetailResponse>(`/v2/questions/${questionId}`);
}

export async function reprocessQuestion(questionId: string): Promise<{
  ok: boolean;
  questionId: string;
  setId: string;
  reviewStatus: string;
}> {
  return apiPost<{
    ok: boolean;
    questionId: string;
    setId: string;
    reviewStatus: string;
  }>(`/v2/questions/${questionId}/reprocess`);
}

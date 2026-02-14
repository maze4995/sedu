import { apiPostJson } from "@/lib/api/client";
import type { HintRequest, HintResponse } from "@/lib/api/v2/types";

export async function requestQuestionHint(
  questionId: string,
  payload: HintRequest,
): Promise<HintResponse> {
  return apiPostJson<HintResponse>(`/v2/questions/${questionId}/hint`, payload);
}

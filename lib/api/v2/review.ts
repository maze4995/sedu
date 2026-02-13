import { apiGet, apiPatchJson } from "@/lib/api/client";
import type {
  ReviewPatchRequest,
  ReviewPatchResponse,
  ReviewQueueResponse,
} from "@/lib/api/v2/types";

export async function getReviewQueue(reviewStatus = "auto_flagged"): Promise<ReviewQueueResponse> {
  return apiGet<ReviewQueueResponse>(`/v2/review/queue?reviewStatus=${encodeURIComponent(reviewStatus)}`);
}

export async function patchQuestionReview(
  questionId: string,
  payload: ReviewPatchRequest,
): Promise<ReviewPatchResponse> {
  return apiPatchJson<ReviewPatchResponse>(`/v2/questions/${questionId}/review`, payload);
}

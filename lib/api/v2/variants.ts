import { apiGet, apiPostJson } from "@/lib/api/client";
import type {
  VariantCreateRequest,
  VariantCreateResponse,
  VariantListResponse,
} from "@/lib/api/v2/types";

export async function listQuestionVariants(questionId: string): Promise<VariantListResponse> {
  return apiGet<VariantListResponse>(`/v2/questions/${questionId}/variants`);
}

export async function createQuestionVariant(
  questionId: string,
  payload: VariantCreateRequest,
): Promise<VariantCreateResponse> {
  return apiPostJson<VariantCreateResponse>(`/v2/questions/${questionId}/variants`, payload);
}

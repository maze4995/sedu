import { apiGet } from "@/lib/api/client";
import type {
  SetDetailResponse,
  SetListResponse,
  QuestionListResponse,
} from "@/lib/api/v2/types";

export async function listSets(params?: {
  limit?: number;
  offset?: number;
  status?: string;
}): Promise<SetListResponse> {
  const search = new URLSearchParams();
  search.set("limit", String(params?.limit ?? 50));
  search.set("offset", String(params?.offset ?? 0));
  if (params?.status && params.status !== "all") search.set("status", params.status);
  return apiGet<SetListResponse>(`/v2/sets?${search.toString()}`);
}

export async function getSet(setId: string): Promise<SetDetailResponse> {
  return apiGet<SetDetailResponse>(`/v2/sets/${setId}`);
}

export async function listQuestionsForSet(setId: string): Promise<QuestionListResponse> {
  return apiGet<QuestionListResponse>(`/v2/sets/${setId}/questions`);
}

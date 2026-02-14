import { apiGet } from "@/lib/api/client";
import type { JobDetailResponse, JobEventListResponse } from "@/lib/api/v2/types";

export async function getJob(jobId: string): Promise<JobDetailResponse> {
  return apiGet<JobDetailResponse>(`/v2/jobs/${jobId}`);
}

export async function getJobEvents(jobId: string): Promise<JobEventListResponse> {
  return apiGet<JobEventListResponse>(`/v2/jobs/${jobId}/events`);
}

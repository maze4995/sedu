import { apiGet, apiPostForm } from "@/lib/api/client";
import type { DocumentCreateResponse, JobDetailResponse } from "@/lib/api/v2/types";

export async function createDocument(file: File): Promise<DocumentCreateResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiPostForm<DocumentCreateResponse>("/v2/documents", formData);
}

export async function getJob(jobId: string): Promise<JobDetailResponse> {
  return apiGet<JobDetailResponse>(`/v2/jobs/${jobId}`);
}

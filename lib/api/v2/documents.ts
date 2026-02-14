import { apiPostForm } from "@/lib/api/client";
import type { DocumentCreateResponse } from "@/lib/api/v2/types";

export async function createDocument(file: File): Promise<DocumentCreateResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiPostForm<DocumentCreateResponse>("/v2/documents", formData);
}

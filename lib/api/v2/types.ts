export type SetStatus =
  | "created"
  | "extracting"
  | "ready"
  | "needs_review"
  | "error"
  | string;

export type ReviewStatus =
  | "unreviewed"
  | "auto_ok"
  | "auto_flagged"
  | "approved"
  | "rejected";

export interface DocumentCreateResponse {
  documentId: string;
  setId: string;
  jobId: string;
  status: string;
}

export interface JobDetailResponse {
  jobId: string;
  setId: string;
  status: string;
  stage?: string | null;
  percent: number;
  errorMessage?: string | null;
}

export interface SetSummary {
  setId: string;
  status: SetStatus;
  title?: string | null;
  questionCount: number;
  sourceFilename?: string | null;
}

export interface SetListResponse {
  sets: SetSummary[];
  limit: number;
  offset: number;
}

export interface SetDetailResponse {
  setId: string;
  status: SetStatus;
  title?: string | null;
  sourceFilename?: string | null;
  sourceMime?: string | null;
  sourceSize?: number | null;
  questionCount: number;
}

export interface QuestionSummary {
  questionId: string;
  numberLabel?: string | null;
  orderIndex: number;
  reviewStatus: ReviewStatus;
  confidence?: number | null;
}

export interface QuestionListResponse {
  setId: string;
  questions: QuestionSummary[];
}

export interface QuestionDetailResponse {
  questionId: string;
  setId: string;
  numberLabel?: string | null;
  orderIndex: number;
  reviewStatus: ReviewStatus;
  confidence?: number | null;
  ocrText?: string | null;
  metadata: Record<string, unknown>;
  structure: Record<string, unknown>;
}

export interface ReviewQueueItem {
  questionId: string;
  setId: string;
  numberLabel?: string | null;
  orderIndex: number;
  reviewStatus: ReviewStatus;
  confidence?: number | null;
  metadata: Record<string, unknown>;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  count: number;
}

export interface ReviewPatchRequest {
  reviewer: string;
  reviewStatus: ReviewStatus;
  note?: string;
  metadataPatch?: Record<string, unknown>;
}

export interface ReviewPatchResponse {
  questionId: string;
  reviewStatus: ReviewStatus;
  metadata: Record<string, unknown>;
}

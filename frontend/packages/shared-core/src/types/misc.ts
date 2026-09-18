/**
 * Misc / cross-cutting type definitions.
 */

export type ReportType = "daily" | "weekly" | "monthly";

export interface Report {
  type: ReportType;
  path: string;
  status: string;
  generated_at?: string;
}

export interface ReportRequest {
  type: ReportType;
}

export interface GenerateReportRequest {
  type: ReportType;
}

export interface HealthStatus {
  status: "ok" | "degraded" | "down";
  version?: string;
  uptime?: number;
}

export interface PaginatedResponse<T = any> {
  items: T[];
  page: number;
  size: number;
  total: number;
}

export interface ApiError {
  error: string;
  message?: string;
}

export interface Poem {
  title?: string;
  author?: string;
  dynasty?: string;
  content: string[];
  tags?: string[];
}

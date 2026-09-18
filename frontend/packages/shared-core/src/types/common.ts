/**
 * Common shared types.
 */

export interface ApiResponse<T = any> {
  data: T;
  error?: string;
  message?: string;
}

export interface Pagination {
  page: number;
  size: number;
  total: number;
}

export interface PaginatedResponse<T = any> {
  items: T[];
  page: number;
  size: number;
  total: number;
}

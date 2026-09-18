/**
 * 小程序兼容版本的 ApiClient 适配器
 * 独立的 wx.request 实现，不继承自 Web ApiClient
 */

import {
  ApiClientConfig,
  ApiError,
  RequestOptions,
  StorageAdapter,
  wxStorageAdapter,
  isWechatMiniProgram,
} from "./mini-types";

export type { ApiClientConfig, ApiError, RequestOptions, StorageAdapter };
export { wxStorageAdapter, isWechatMiniProgram };

/**
 * 小程序兼容的 ApiClient 实现
 * 使用 wx.request 替代 fetch，保持相同接口
 */
export class MiniApiClient {
  private baseURL: string;
  private storage: StorageAdapter;
  private tokenKey: string;
  private onUnauthorized?: () => void;
  private defaultTimeout: number;
  private externalGetToken?: () => string | null | Promise<string | null>;

  constructor(config: ApiClientConfig) {
    this.baseURL = config.baseURL.replace(/\/$/, '');
    this.storage = config.storage || wxStorageAdapter();
    this.tokenKey = config.tokenKey || 'looma_token';
    this.onUnauthorized = config.onUnauthorized;
    this.defaultTimeout = config.timeout || 30000;
    this.externalGetToken = config.getToken;
  }

  private async getToken(): Promise<string | null> {
    if (this.externalGetToken) {
      const result = this.externalGetToken();
      return Promise.resolve(result);
    }
    return this.storage.getItem(this.tokenKey);
  }

  /** Store a token in the configured storage adapter. */
  async setToken(token: string): Promise<void> {
    await this.storage.setItem(this.tokenKey, token);
  }

  /** Remove the stored token. Called automatically on 401 responses. */
  async clearToken(): Promise<void> {
    await this.storage.removeItem(this.tokenKey);
  }

  private buildQueryString(params?: Record<string, any>): string {
    if (!params) return '';
    const parts: string[] = [];
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null) continue;
      if (Array.isArray(value)) {
        for (const item of value) {
          parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(item))}`);
        }
      } else {
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
      }
    }
    return parts.length ? `?${parts.join('&')}` : '';
  }

  private async buildHeaders(
    extraHeaders?: Record<string, string>,
    includeAuth = true
  ): Promise<Record<string, string>> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...extraHeaders,
    };

    if (includeAuth) {
      const token = await this.getToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
    }

    return headers;
  }

  private parseWxError(resp: any): Record<string, any> {
    try {
      const data = resp.data;
      return typeof data === 'object' && data !== null ? data : { message: String(data) };
    } catch {
      return { message: resp.statusText || `HTTP ${resp.statusCode}` };
    }
  }

  /**
   * 核心请求方法包装 wx.request
   */
  private async request<T = any>(
    method: string,
    url: string,
    data?: any,
    options: RequestOptions = {}
  ): Promise<T> {
    const query = this.buildQueryString(options.params);
    const fullUrl = `${this.baseURL}${url}${query}`;
    
    const headers = await this.buildHeaders(
      options.headers,
      true // includeAuth
    );

    return new Promise((resolve, reject) => {
      const timeoutMs = options.timeout ?? this.defaultTimeout;
      
      // 小程序请求配置
      const requestConfig: any = {
        url: fullUrl,
        method: method as any,
        data: data,
        header: headers,
        timeout: timeoutMs,
        success: (resp: any) => {
          if (resp.statusCode >= 200 && resp.statusCode < 300) {
            resolve(resp.data as T);
          } else if (resp.statusCode === 401) {
            this.clearToken();
            this.onUnauthorized?.();
            const error = this.parseWxError(resp);
            reject(new ApiError(resp.statusCode, error, 'Unauthorized'));
          } else {
            const error = this.parseWxError(resp);
            reject(new ApiError(resp.statusCode, error, `HTTP ${resp.statusCode}`));
          }
        },
        fail: (err: any) => {
          let errMsg = err.errMsg || '网络错误';
          if (errMsg.includes('timeout')) {
            errMsg = 'request_timeout';
          } else if (errMsg.includes('fail')) {
            errMsg = `网络连接失败 (${this.baseURL})`;
          }
          reject(new Error(errMsg));
        }
      };

      // 小程序请求
      wx.request(requestConfig);
    });
  }

  async get<T = any>(url: string, params?: Record<string, any>, options?: RequestOptions): Promise<T> {
    return this.request<T>('GET', url, undefined, { ...options, params });
  }

  async post<T = any>(url: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>('POST', url, data, options);
  }

  async put<T = any>(url: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>('PUT', url, data, options);
  }

  async delete<T = any>(url: string, params?: Record<string, any>, options?: RequestOptions): Promise<T> {
    return this.request<T>('DELETE', url, undefined, { ...options, params });
  }

  /**
   * 小程序不支持 FormData 文件上传，需要特殊处理
   * 这里提供一个兼容性实现，实际使用时可能需要使用 wx.uploadFile
   */
  async upload<T = any>(
    url: string,
    file: any,
    fieldName = "file",
    _options?: RequestOptions,
  ): Promise<T> {
    return new Promise((resolve, reject) => {
      void this.getToken().then((token) => {
        const header: Record<string, string> = {};
        if (token) {
          header.Authorization = `Bearer ${token}`;
        }

        wx.uploadFile({
          url: `${this.baseURL}${url}`,
          filePath: file.path || file.tempFilePath,
          name: fieldName,
          header,
          success: (resp: WechatUploadResponse) => {
            if (resp.statusCode >= 200 && resp.statusCode < 300) {
              try {
                const data = JSON.parse(resp.data);
                resolve(data as T);
              } catch {
                resolve(resp.data as unknown as T);
              }
            } else {
              reject(new Error(`Upload failed: ${resp.statusCode}`));
            }
          },
          fail: (err: { errMsg?: string }) => {
            reject(new Error(err.errMsg || "Upload failed"));
          },
        });
      });
    });
  }

  /** SSE not supported in miniprogram — use non-streaming POST /v1/ask instead. */
  async stream(_url: string, _data?: any, _options?: RequestOptions): Promise<void> {
    throw new Error("SSE streaming not supported in miniprogram environment");
  }
}

interface WechatUploadResponse {
  statusCode: number;
  data: string;
}

declare const wx: {
  request: (config: Record<string, unknown>) => void;
  uploadFile: (config: Record<string, unknown>) => void;
  getStorageSync: (key: string) => unknown;
  setStorageSync: (key: string, data: string) => void;
  removeStorageSync: (key: string) => void;
};

/**
 * 创建小程序专用的 ApiClient 实例
 */
export function createMiniApiClient(config: ApiClientConfig): MiniApiClient {
  const finalConfig: ApiClientConfig = {
    ...config,
    storage: config.storage || wxStorageAdapter(),
  };
  return new MiniApiClient(finalConfig);
}

/** Pick MiniApiClient in WeChat; Web callers should use createApiClient from ApiClient.ts */
export function createPlatformAwareApiClient(config: ApiClientConfig): MiniApiClient {
  return createMiniApiClient(config);
}
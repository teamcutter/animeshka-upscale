// Thin client for the FastAPI backend. All URLs are relative: Vite (dev) and nginx (Docker)
// proxy /api and /health to the API, so no base URL or CORS configuration is needed.
import axios, { isAxiosError, isCancel } from 'axios';

export type Mode = '2k' | '4k';
export type JobStatus = 'queued' | 'processing' | 'done' | 'failed';

export interface FileInfo {
  size_bytes: number;
  width: number | null;
  height: number | null;
}

export interface Job {
  id: string;
  kind: 'image' | 'video';
  mode: Mode;
  status: JobStatus;
  filename: string;
  max_size: number;
  start_seconds: number;
  end_seconds: number | null;
  input: FileInfo;
  output: FileInfo | null;
  metrics: Record<string, number>;
  result_url: string | null;
  original_url: string;
  error: string | null;
  published: boolean;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Health {
  status: 'ok' | 'degraded';
  database: 'ok' | 'unavailable';
  backend: 'stub' | 'realesrgan';
  worker: 'embedded' | 'external';
  auth: 'required' | 'open';
  modes: Record<Mode, boolean>;
}

export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

// The session is an HttpOnly cookie set by the server; the browser sends it on its own.
const http = axios.create({ baseURL: '/', withCredentials: true });

export async function getMe(signal?: AbortSignal): Promise<User> {
  const { data } = await http.get<User>('/api/auth/me', { signal });
  return data;
}

export async function login(email: string, password: string): Promise<User> {
  const { data } = await http.post<User>('/api/auth/login', { email, password });
  return data;
}

export async function register(email: string, password: string, name: string): Promise<User> {
  const { data } = await http.post<User>('/api/auth/register', { email, password, name });
  return data;
}

export async function logout(): Promise<void> {
  await http.post('/api/auth/logout');
}

export async function deleteJob(id: string): Promise<void> {
  await http.delete(`/api/jobs/${id}`);
}

/** The shared account anonymous requests run as when the server has AUTH__REQUIRED=false. */
export const GUEST_EMAIL = 'guest@animeshka.local';

export async function getHealth(signal?: AbortSignal): Promise<Health> {
  // 503 = database down; the body still describes the server, so accept it.
  const { data } = await http.get<Health>('/health', {
    signal,
    validateStatus: (status) => status === 200 || status === 503,
  });
  return data;
}

export interface UploadOptions {
  maxSize?: number;
  startSeconds?: number;
  endSeconds?: number;
  signal?: AbortSignal;
  onProgress?: (fraction: number) => void;
}

export type MediaKind = Job['kind'];

/** POST /api/upscale (image) or /api/upscale/video; the server answers 202 with the queued job. */
export async function uploadMedia(
  file: File,
  kind: MediaKind,
  mode: Mode,
  { maxSize, startSeconds, endSeconds, signal, onProgress }: UploadOptions = {},
): Promise<Job> {
  const form = new FormData();
  form.append('file', file);
  form.append('mode', mode);
  if (maxSize) form.append('max_size', String(maxSize));
  if (kind === 'video') {
    if (startSeconds !== undefined) form.append('start_seconds', String(startSeconds));
    if (endSeconds !== undefined) form.append('end_seconds', String(endSeconds));
  }

  const url = kind === 'video' ? '/api/upscale/video' : '/api/upscale';
  const { data } = await http.post<Job>(url, form, {
    signal,
    onUploadProgress: (event) => {
      if (onProgress && event.total) onProgress(event.loaded / event.total);
    },
  });
  return data;
}

export async function previewVideo(
  file: File, startSeconds: number, durationSeconds: number, signal?: AbortSignal,
): Promise<{ blob: Blob; duration: number }> {
  const form = new FormData();
  form.append('file', file);
  form.append('start_seconds', String(startSeconds));
  form.append('duration_seconds', String(durationSeconds));
  const response = await http.post<Blob>('/api/upscale/video/preview', form, {
    signal, responseType: 'blob',
  });
  return { blob: response.data, duration: Number(response.headers['x-video-duration']) };
}

export async function getJob(id: string, signal?: AbortSignal): Promise<Job> {
  const { data } = await http.get<Job>(`/api/jobs/${id}`, { signal });
  return data;
}

export function downloadName(job: Job): string {
  const base = job.filename.replace(/\.[^.]+$/, '') || 'upscaled';
  return `${base}_${job.mode}.${job.kind === 'video' ? 'mp4' : 'png'}`;
}

export async function listJobs(
  params: { status?: JobStatus; limit?: number; offset?: number } = {},
  signal?: AbortSignal,
): Promise<Job[]> {
  const { data } = await http.get<Job[]>('/api/jobs', { params, signal });
  return data;
}

export interface WaitOptions {
  signal?: AbortSignal;
  intervalMs?: number;
  onUpdate?: (job: Job) => void;
}

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });

/** Poll a job until it is done or failed (jobs run in the background on the server). */
export async function waitForJob(
  id: string,
  { signal, intervalMs = 1000, onUpdate }: WaitOptions = {},
): Promise<Job> {
  for (;;) {
    const job = await getJob(id, signal);
    onUpdate?.(job);
    if (job.status === 'done' || job.status === 'failed') return job;
    await sleep(intervalMs, signal);
  }
}

// --- Public feed: publishing, likes, comments ---------------------------------------------

export interface FeedItem {
  id: string;
  author: { name: string };
  mine: boolean;
  kind: MediaKind;
  mode: Mode;
  input: FileInfo;
  output: FileInfo;
  media_url: string;
  original_url: string;
  like_count: number;
  liked: boolean;
  comment_count: number;
  published_at: string;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface Comment {
  id: string;
  post_id: string;
  author: { name: string };
  mine: boolean;
  can_delete: boolean;
  text: string;
  created_at: string;
}

/** Share any finished job (image or video, new or old) in the public feed. */
export async function publishJob(id: string): Promise<Job> {
  const { data } = await http.post<Job>(`/api/jobs/${id}/publish`);
  return data;
}

/** Take the job out of the feed (its likes and comments are removed too). */
export async function unpublishJob(id: string): Promise<Job> {
  const { data } = await http.delete<Job>(`/api/jobs/${id}/publish`);
  return data;
}

export async function getFeed(
  cursor?: string | null, limit = 12, signal?: AbortSignal,
): Promise<Page<FeedItem>> {
  const { data } = await http.get<Page<FeedItem>>('/api/feed', {
    params: { limit, ...(cursor ? { cursor } : {}) },
    signal,
  });
  return data;
}

/** Like or unlike; the server answers with the post's new counts. */
export async function setLiked(postId: string, liked: boolean): Promise<FeedItem> {
  const url = `/api/feed/${postId}/like`;
  const { data } = liked ? await http.put<FeedItem>(url) : await http.delete<FeedItem>(url);
  return data;
}

export async function getComments(
  postId: string, cursor?: string | null, signal?: AbortSignal,
): Promise<Page<Comment>> {
  const { data } = await http.get<Page<Comment>>(`/api/feed/${postId}/comments`, {
    params: { limit: 50, ...(cursor ? { cursor } : {}) },
    signal,
  });
  return data;
}

export async function addComment(postId: string, text: string): Promise<Comment> {
  const { data } = await http.post<Comment>(`/api/feed/${postId}/comments`, { text });
  return data;
}

export async function deleteComment(postId: string, commentId: string): Promise<void> {
  await http.delete(`/api/feed/${postId}/comments/${commentId}`);
}

export function isAbort(error: unknown): boolean {
  return isCancel(error) || (error instanceof DOMException && error.name === 'AbortError');
}

/** Human-readable message from a failed request (FastAPI puts it in `detail`). */
export function errorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item: { msg?: string }) => item.msg ?? JSON.stringify(item))
        .join('; ');
    }
    if (error.response?.status === 401) return 'Нужно войти в аккаунт';
    if (error.response) return `Сервер ответил ${error.response.status}`;
    return 'Сервер недоступен';
  }
  return error instanceof Error ? error.message : String(error);
}

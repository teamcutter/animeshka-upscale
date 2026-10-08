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
  input: FileInfo;
  output: FileInfo | null;
  metrics: Record<string, number>;
  result_url: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface Health {
  status: 'ok' | 'degraded';
  database: 'ok' | 'unavailable';
  backend: 'stub' | 'realesrgan';
  worker: 'embedded' | 'external';
  modes: Record<Mode, boolean>;
}

const http = axios.create({ baseURL: '/' });

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
  signal?: AbortSignal;
  onProgress?: (fraction: number) => void;
}

export type MediaKind = Job['kind'];

/** POST /api/upscale (image) or /api/upscale/video; the server answers 202 with the queued job. */
export async function uploadMedia(
  file: File,
  kind: MediaKind,
  mode: Mode,
  { maxSize, signal, onProgress }: UploadOptions = {},
): Promise<Job> {
  const form = new FormData();
  form.append('file', file);
  form.append('mode', mode);
  if (kind === 'image' && maxSize) form.append('max_size', String(maxSize));

  const url = kind === 'video' ? '/api/upscale/video' : '/api/upscale';
  const { data } = await http.post<Job>(url, form, {
    signal,
    onUploadProgress: (event) => {
      if (onProgress && event.total) onProgress(event.loaded / event.total);
    },
  });
  return data;
}

export async function getJob(id: string, signal?: AbortSignal): Promise<Job> {
  const { data } = await http.get<Job>(`/api/jobs/${id}`, { signal });
  return data;
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
    if (error.response) return `Сервер ответил ${error.response.status}`;
    return 'Сервер недоступен';
  }
  return error instanceof Error ? error.message : String(error);
}

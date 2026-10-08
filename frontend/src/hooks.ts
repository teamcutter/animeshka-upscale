import { useEffect, useState } from 'react';

import { getHealth, isAbort, type Health } from './api';

/** Server status from /health; re-fetched whenever `refreshKey` changes. */
export function useHealth(refreshKey: unknown = null) {
  const [health, setHealth] = useState<Health | null>(null);
  const [unreachable, setUnreachable] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then((data) => {
        setHealth(data);
        setUnreachable(false);
      })
      .catch((error: unknown) => {
        if (!isAbort(error)) setUnreachable(true);
      });
    return () => controller.abort();
  }, [refreshKey]);

  return { health, unreachable };
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' });
}

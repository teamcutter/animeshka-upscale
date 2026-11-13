import { useEffect, useRef, useState } from 'react';
import { Loader2, MessageSquare } from 'lucide-react';

import { errorMessage, getFeed, isAbort, type FeedItem } from '../api';
import { formatDate } from '../hooks';
import LikeButton from './LikeButton';
import PostModal from './PostModal';

export default function FeedTab() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  // State changes only after the request: the first page is fetched straight from an effect.
  const fetchPage = async (from: string | null) => {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    try {
      const page = await getFeed(from, 12, request.signal);
      setError('');
      setItems((prev) => {
        // Skip posts already shown (the feed may have moved between pages).
        const known = new Set(from ? prev.map((item) => item.id) : []);
        return [...(from ? prev : []), ...page.items.filter((item) => !known.has(item.id))];
      });
      setCursor(page.next_cursor);
    } catch (err) {
      if (!isAbort(err)) setError(errorMessage(err));
    } finally {
      if (!request.signal.aborted) setLoading(false);
    }
  };

  const load = (from: string | null) => {
    setLoading(true);
    setError('');
    void fetchPage(from);
  };

  useEffect(() => {
    const request = new AbortController();
    controller.current = request;
    getFeed(null, 12, request.signal)
      .then((page) => {
        setItems(page.items);
        setCursor(page.next_cursor);
      })
      .catch((err: unknown) => {
        if (!isAbort(err)) setError(errorMessage(err));
      })
      .finally(() => {
        if (!request.signal.aborted) setLoading(false);
      });
    return () => controller.current?.abort();
  }, []);

  const update = (changed: FeedItem) =>
    setItems((prev) => prev.map((item) => (item.id === changed.id ? changed : item)));

  const opened = items.find((item) => item.id === openId) ?? null;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap justify-between items-end gap-4 border-l-4 border-orange-500 pl-6 py-2">
        <div>
          <h2 className="text-3xl font-black text-white uppercase tracking-tighter">Общая лента</h2>
          <p className="text-zinc-500 font-mono text-sm uppercase mt-1">PUBLISHED_WORKS</p>
        </div>
        <button
          onClick={() => load(null)}
          disabled={loading}
          className="text-orange-500 border border-orange-500 px-3 py-1 font-mono text-xs font-bold uppercase hover:bg-orange-500 hover:text-black transition-colors disabled:opacity-50"
        >
          Обновить
        </button>
      </div>

      {error && (
        <div className="border border-red-500/50 bg-red-500/10 text-red-400 font-mono text-sm p-4">{error}</div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="border border-dashed border-zinc-800 p-12 text-center font-mono text-sm text-zinc-500 uppercase">
          Лента пуста. Опубликуйте работу из «Мои работы» или сразу после обработки.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {items.map((item) => (
          <article
            key={item.id}
            onClick={() => setOpenId(item.id)}
            className="border border-zinc-800 bg-zinc-900 flex flex-col group hover:border-orange-500 transition-colors cursor-pointer"
          >
            <div className="h-56 bg-zinc-950 border-b border-zinc-800 relative overflow-hidden">
              {item.kind === 'video' ? (
                <video src={item.media_url} muted playsInline preload="metadata" className="h-full w-full object-cover" />
              ) : (
                <img src={item.media_url} alt={`Работа ${item.author.name}`} loading="lazy" className="h-full w-full object-cover" />
              )}
              <span className="absolute top-2 left-2 bg-black/80 border border-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-300 uppercase">
                {item.kind === 'video' ? 'VID' : 'IMG'} · {item.output.width}×{item.output.height}
              </span>
            </div>

            <div className="p-5 flex-1 flex flex-col">
              <div className="flex justify-between items-start mb-4">
                <h3 className="font-bold text-white text-lg truncate pr-2 uppercase tracking-wide">
                  @{item.author.name}
                  {item.mine && <span className="ml-2 text-xs text-orange-500 font-mono">(вы)</span>}
                </h3>
                <span className="bg-orange-500/10 text-orange-500 border border-orange-500/50 px-2 py-1 text-xs font-mono font-bold whitespace-nowrap uppercase">
                  x{item.mode === '4k' ? 4 : 2}_{item.mode}
                </span>
              </div>
              <div className="mt-auto pt-4 border-t border-zinc-800 flex justify-between items-center gap-2 text-sm font-mono text-zinc-500">
                <span className="text-xs">{formatDate(item.published_at)}</span>
                <div className="flex items-center gap-2">
                  <LikeButton item={item} onChange={update} />
                  <span className="flex items-center gap-1.5 px-2 py-1 border border-zinc-800 text-zinc-400 text-xs font-bold group-hover:border-zinc-600">
                    <MessageSquare size={14} />
                    {item.comment_count}
                  </span>
                </div>
              </div>
            </div>
          </article>
        ))}
      </div>

      {loading && (
        <div className="flex justify-center py-6 text-orange-500">
          <Loader2 className="animate-spin" />
        </div>
      )}
      {!loading && cursor && (
        <div className="flex justify-center">
          <button
            onClick={() => load(cursor)}
            className="border border-zinc-800 px-6 py-3 font-mono text-xs font-bold uppercase text-zinc-300 hover:border-orange-500 hover:text-orange-500 transition-colors"
          >
            Показать ещё
          </button>
        </div>
      )}

      {opened && <PostModal key={opened.id} item={opened} onChange={update} onClose={() => setOpenId(null)} />}
    </div>
  );
}

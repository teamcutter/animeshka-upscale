import { useEffect, useMemo, useRef, useState } from 'react';
import { Hash, Loader2, MessageSquare, Search, X } from 'lucide-react';

import { errorMessage, getFeed, isAbort, type FeedItem } from '../api';
import { formatDate } from '../hooks';
import LikeButton from './LikeButton';
import PostModal from './PostModal';

const QUICK_TAGS = ['#4k', '#2k', '#vid', '#img'];

interface FeedPost extends FeedItem {
  caption?: string | null;
}

function renderTextWithTags(text: string, onSelectTag: (tag: string) => void) {
  const parts = text.split(/(#[\p{L}\p{N}_]+)/gu);
  return parts.map((part, idx) => {
    if (/^#[\p{L}\p{N}_]+$/u.test(part)) {
      return (
        <button
          key={`${part}-${idx}`}
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onSelectTag(part.toLowerCase());
          }}
          className="text-teal-400 hover:underline font-bold"
        >
          {part}
        </button>
      );
    }
    return <span key={idx}>{part}</span>;
  });
}

export default function FeedTab() {
  const [items, setItems] = useState<FeedPost[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const controller = useRef<AbortController | null>(null);

  const fetchPage = async (from: string | null) => {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    try {
      const page = await getFeed(from, 12, request.signal);
      setError('');
      setItems((prev) => {
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
    setItems((prev) => prev.map((item) => (item.id === changed.id ? { ...item, ...changed } : item)));

  const selectTag = (tag: string) => {
    const clean = tag.toLowerCase();
    setQuery((prev) => {
      const parts = prev.trim().split(/\s+/).filter(Boolean);
      const exists = parts.some((p) => p.toLowerCase() === clean);
      if (exists) return parts.filter((p) => p.toLowerCase() !== clean).join(' ');
      return [...parts, clean].join(' ');
    });
  };

  const normalizedQuery = query.trim().toLowerCase();

  const filteredItems = useMemo(() => {
    if (!normalizedQuery) return items;
    const tokens = normalizedQuery.split(/\s+/).filter(Boolean);

    return items.filter((item) => {
      const caption = (item.caption ?? '').toLowerCase();
      const author = item.author.name.toLowerCase();
      const autoTags = [
        `#${item.mode}`,
        `#x${item.mode === '4k' ? 4 : 2}`,
        `#${item.kind}`,
        item.kind === 'video' ? '#vid' : '#img',
      ].join(' ');
      const haystack = `${author} ${caption} ${item.mode} ${item.kind} ${autoTags}`;
      return tokens.every((token) => haystack.includes(token));
    });
  }, [items, normalizedQuery]);

  const opened = items.find((item) => item.id === openId) ?? null;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap justify-between items-end gap-4 border-l-4 border-teal-400 pl-6 py-2">
        <div>
          <h2 className="text-3xl font-black text-white uppercase tracking-tighter">Общая лента</h2>
          <p className="text-zinc-500 font-mono text-sm uppercase mt-1">PUBLISHED_WORKS</p>
        </div>
        <button
          type="button"
          onClick={() => load(null)}
          disabled={loading}
          className="text-teal-400 border border-teal-400/70 px-3 py-1 font-mono text-xs font-bold uppercase hover:bg-teal-400 hover:text-black transition-colors disabled:opacity-50"
        >
          Обновить
        </button>
      </div>

      <div className="border border-zinc-800 bg-zinc-900 p-4 space-y-3">
        <div className="flex items-center gap-3 bg-zinc-950 border border-zinc-800 px-3 py-2 focus-within:border-teal-400 transition-colors">
          <Search size={16} className="text-teal-400 shrink-0" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск по тексту или #хештегам..."
            className="w-full bg-transparent text-white font-mono text-sm placeholder-zinc-600 focus:outline-none"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              aria-label="Очистить поиск"
              className="text-zinc-500 hover:text-white transition-colors"
            >
              <X size={16} />
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 text-zinc-500 uppercase">
              <Hash size={12} /> Теги:
            </span>
            {QUICK_TAGS.map((tag) => {
              const active = query.toLowerCase().includes(tag.toLowerCase());
              return (
                <button
                  key={tag}
                  type="button"
                  onClick={() => selectTag(tag)}
                  className={`px-2.5 py-1 border uppercase transition-colors ${
                    active
                      ? 'border-teal-400 bg-teal-400 text-black font-bold'
                      : 'border-zinc-800 bg-zinc-950 text-zinc-400 hover:border-zinc-600 hover:text-white'
                  }`}
                >
                  {tag}
                </button>
              );
            })}
          </div>
          <span className="text-zinc-500 uppercase">
            Найдено: {filteredItems.length} / {items.length}
          </span>
        </div>
      </div>

      {error && (
        <div className="border border-red-500/50 bg-red-500/10 text-red-400 font-mono text-sm p-4">{error}</div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="border border-dashed border-zinc-800 p-12 text-center font-mono text-sm text-zinc-500 uppercase">
          Лента пуста. Опубликуйте работу из «Мои работы» или сразу после обработки.
        </div>
      )}

      {!loading && !error && items.length > 0 && filteredItems.length === 0 && (
        <div className="border border-dashed border-zinc-800 p-10 text-center font-mono text-sm text-zinc-500 uppercase space-y-3">
          <p>По запросу «{query}» ничего не найдено.</p>
          <button
            type="button"
            onClick={() => setQuery('')}
            className="text-teal-400 border border-teal-400/70 px-3 py-1 text-xs font-bold hover:bg-teal-400 hover:text-black transition-colors"
          >
            Сбросить фильтр
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredItems.map((item) => {
          const caption = (item.caption ?? '').trim();

          return (
            <article
              key={item.id}
              onClick={() => setOpenId(item.id)}
              className="border border-zinc-800 bg-zinc-900 flex flex-col group hover:border-teal-400 transition-colors cursor-pointer"
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
                <div className="flex justify-between items-start mb-3">
                  <h3 className="font-bold text-white text-lg truncate pr-2 uppercase tracking-wide">
                    @{item.author.name}
                    {item.mine && <span className="ml-2 text-xs text-teal-400 font-mono">(вы)</span>}
                  </h3>
                  <span className="bg-teal-400/10 text-teal-400 border border-teal-400/40 px-2 py-1 text-xs font-mono font-bold whitespace-nowrap uppercase">
                    x{item.mode === '4k' ? 4 : 2}_{item.mode}
                  </span>
                </div>

                {caption && (
                  <p className="text-zinc-300 font-mono text-xs leading-relaxed mb-4 line-clamp-3 break-words">
                    {renderTextWithTags(caption, selectTag)}
                  </p>
                )}

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
          );
        })}
      </div>

      {loading && (
        <div className="flex justify-center py-6 text-teal-400">
          <Loader2 className="animate-spin" />
        </div>
      )}
      {!loading && cursor && (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={() => load(cursor)}
            className="border border-zinc-800 px-6 py-3 font-mono text-xs font-bold uppercase text-zinc-300 hover:border-teal-400 hover:text-teal-400 transition-colors"
          >
            Показать ещё
          </button>
        </div>
      )}

      {opened && <PostModal key={opened.id} item={opened} onChange={update} onClose={() => setOpenId(null)} />}
    </div>
  );
}
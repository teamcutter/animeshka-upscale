import { useEffect, useRef, useState } from 'react';
import { Loader2, Send, Trash2, X } from 'lucide-react';

import {
  addComment,
  deleteComment,
  errorMessage,
  getComments,
  isAbort,
  type Comment,
  type FeedItem,
} from '../api';
import { formatDate } from '../hooks';
import LikeButton from './LikeButton';
import MediaComparison from './MediaComparison';

const MAX_COMMENT = 1000;

interface Props {
  item: FeedItem;
  onChange: (item: FeedItem) => void;
  onClose: () => void;
}

/** A post opened from the feed: the work full size, likes and the comment thread. */
export default function PostModal({ item, onChange, onClose }: Props) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const listEnd = useRef<HTMLDivElement>(null);

  const fetchPage = async (from: string | null) => {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    try {
      const page = await getComments(item.id, from, request.signal);
      setComments((prev) => [...(from ? prev : []), ...page.items]);
      setCursor(page.next_cursor);
    } catch (err) {
      if (!isAbort(err)) setError(errorMessage(err));
    } finally {
      if (!request.signal.aborted) setLoading(false);
    }
  };

  const loadMore = (from: string) => {
    setLoading(true);
    void fetchPage(from);
  };

  // The feed remounts this window per post (key={id}), so the thread loads once on mount.
  useEffect(() => {
    const request = new AbortController();
    controller.current = request;
    getComments(item.id, null, request.signal)
      .then((page) => {
        setComments(page.items);
        setCursor(page.next_cursor);
      })
      .catch((err: unknown) => {
        if (!isAbort(err)) setError(errorMessage(err));
      })
      .finally(() => {
        if (!request.signal.aborted) setLoading(false);
      });
    return () => controller.current?.abort();
  }, [item.id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
    };
  }, [onClose]);

  const send = async () => {
    const value = text.trim();
    if (!value || sending) return;
    setSending(true);
    setError('');
    try {
      const created = await addComment(item.id, value);
      setComments((prev) => [...prev, created]);
      setText('');
      onChange({ ...item, comment_count: item.comment_count + 1 });
      requestAnimationFrame(() => listEnd.current?.scrollIntoView({ behavior: 'smooth' }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  };

  const remove = async (comment: Comment) => {
    setError('');
    try {
      await deleteComment(item.id, comment.id);
      setComments((prev) => prev.filter((c) => c.id !== comment.id));
      onChange({ ...item, comment_count: Math.max(0, item.comment_count - 1) });
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <div
      className="fixed inset-0 z-[100] bg-black/80 flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Пост @${item.author.name}`}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-zinc-950 border border-zinc-800 w-full max-w-6xl max-h-[92vh] grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_380px] overflow-hidden shadow-[8px_8px_0px_#ea580c]"
      >
        <MediaComparison kind={item.kind} originalUrl={item.original_url} resultUrl={item.media_url} input={item.input} output={item.output} className="h-[45vh] min-h-[280px] lg:h-full lg:min-h-[560px]" />

        <aside className="flex flex-col min-h-0 max-h-[92vh] border-t lg:border-t-0 lg:border-l border-zinc-800">
          <header className="flex items-start justify-between gap-3 p-5 border-b border-zinc-800">
            <div className="min-w-0">
              <h3 className="font-black text-white text-lg uppercase truncate">@{item.author.name}</h3>
              <p className="font-mono text-xs text-zinc-500 mt-1">
                {formatDate(item.published_at)} · {item.kind === 'video' ? 'VIDEO' : 'IMAGE'} · {item.mode.toUpperCase()}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <LikeButton item={item} onChange={onChange} />
              <button onClick={onClose} aria-label="Закрыть" className="p-1 border border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-600">
                <X size={16} />
              </button>
            </div>
          </header>

          <div className="flex-1 min-h-[160px] overflow-y-auto p-5 space-y-4">
            <p className="font-mono text-xs uppercase text-zinc-500">Комментарии · {item.comment_count}</p>
            {!loading && comments.length === 0 && (
              <p className="text-sm text-zinc-500">Пока никто не написал. Будьте первым!</p>
            )}
            {comments.map((comment) => (
              <div key={comment.id} className="group border-l-2 border-zinc-800 pl-3 hover:border-orange-500 transition-colors">
                <div className="flex items-center justify-between gap-2">
                  <span className={`font-bold text-sm ${comment.mine ? 'text-orange-500' : 'text-white'}`}>
                    @{comment.author.name}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-zinc-600">{formatDate(comment.created_at)}</span>
                    {comment.can_delete && (
                      <button
                        onClick={() => void remove(comment)}
                        aria-label="Удалить комментарий"
                        title="Удалить"
                        className="text-zinc-600 hover:text-red-500 opacity-60 group-hover:opacity-100"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                </div>
                <p className="text-sm text-zinc-300 whitespace-pre-wrap break-words mt-1">{comment.text}</p>
              </div>
            ))}
            {loading && <Loader2 className="animate-spin text-orange-500 mx-auto" />}
            {!loading && cursor && (
              <button onClick={() => loadMore(cursor)} className="font-mono text-xs uppercase text-orange-500 hover:underline">
                Показать ещё
              </button>
            )}
            <div ref={listEnd} />
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send();
            }}
            className="border-t border-zinc-800 p-4 space-y-2"
          >
            {error && <p className="text-red-400 font-mono text-xs">{error}</p>}
            <div className="flex gap-2">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value.slice(0, MAX_COMMENT))}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    void send();
                  }
                }}
                rows={2}
                placeholder="Написать комментарий…"
                className="flex-1 resize-none bg-zinc-900 border border-zinc-800 p-2 text-sm text-white focus:border-orange-500 focus:outline-none"
              />
              <button
                type="submit"
                disabled={sending || !text.trim()}
                aria-label="Отправить"
                className="px-3 bg-orange-500 text-black font-bold hover:bg-orange-400 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              </button>
            </div>
            <p className="font-mono text-[10px] text-zinc-600 text-right">
              Enter — отправить, Shift+Enter — новая строка · {text.length}/{MAX_COMMENT}
            </p>
          </form>
        </aside>
      </div>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { Loader2, Send, X } from 'lucide-react';

const SUGGESTED_TAGS = ['#anime', '#4k', '#2k', '#upscale', '#art'];
const MAX_CAPTION = 500;

interface Props {
  title: string;
  submitting?: boolean;
  error?: string;
  onConfirm: (caption: string) => void | Promise<void>;
  onClose: () => void;
}

export default function PublishModal({ title, submitting = false, error = '', onConfirm, onClose }: Props) {
  const [caption, setCaption] = useState('');

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !submitting) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, submitting]);

  const appendTag = (tag: string) => {
    setCaption((prev) => {
      if (prev.toLowerCase().includes(tag.toLowerCase())) return prev;
      const spacer = prev.trim().length > 0 ? ' ' : '';
      return `${prev.trimEnd()}${spacer}${tag}`.slice(0, MAX_CAPTION);
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    void onConfirm(caption.trim());
  };

  return (
    <div
      className="fixed inset-0 z-[100] bg-black/80 flex items-center justify-center p-4"
      onClick={() => !submitting && onClose()}
      role="dialog"
      aria-modal="true"
      aria-label="Публикация в ленту"
    >
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleSubmit}
        className="w-full max-w-lg bg-zinc-950 border border-zinc-800 p-6 space-y-5 shadow-[8px_8px_0px_#2dd4bf]"
      >
        <div className="flex items-start justify-between gap-3 border-l-4 border-teal-400 pl-4">
          <div className="min-w-0">
            <h3 className="text-xl font-black text-white uppercase tracking-tight">Опубликовать в ленту</h3>
            <p className="font-mono text-xs text-zinc-500 truncate mt-1 uppercase">{title}</p>
          </div>
          <button
            type="button"
            disabled={submitting}
            onClick={onClose}
            aria-label="Закрыть"
            className="p-1 border border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-600 disabled:opacity-50"
          >
            <X size={16} />
          </button>
        </div>

        <div className="space-y-2">
          <label className="block font-mono text-xs uppercase text-zinc-400">
            Описание и #хештеги
          </label>
          <textarea
            autoFocus
            rows={4}
            value={caption}
            onChange={(e) => setCaption(e.target.value.slice(0, MAX_CAPTION))}
            placeholder="Напиши описание и добавь #хештеги..."
            className="w-full resize-none bg-zinc-900 border border-zinc-800 p-3 font-mono text-sm text-white placeholder-zinc-600 focus:border-teal-400 focus:outline-none"
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap gap-1.5">
              {SUGGESTED_TAGS.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => appendTag(tag)}
                  className="px-2 py-0.5 border border-zinc-800 bg-zinc-900 font-mono text-[11px] text-zinc-400 hover:border-teal-400 hover:text-teal-400 transition-colors"
                >
                  +{tag}
                </button>
              ))}
            </div>
            <span className="font-mono text-[11px] text-zinc-600">
              {caption.length}/{MAX_CAPTION}
            </span>
          </div>
        </div>

        {error && (
          <div className="border border-red-500/50 bg-red-500/10 text-red-400 font-mono text-xs p-3">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2 border-t border-zinc-800">
          <button
            type="button"
            disabled={submitting}
            onClick={onClose}
            className="border border-zinc-800 px-4 py-2.5 font-mono text-xs uppercase text-zinc-400 hover:text-white hover:border-zinc-600 disabled:opacity-50"
          >
            Отмена
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-2 bg-teal-400 text-black px-5 py-2.5 font-mono text-xs font-black uppercase tracking-wider hover:bg-teal-300 disabled:opacity-50"
          >
            {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            Опубликовать
          </button>
        </div>
      </form>
    </div>
  );
}
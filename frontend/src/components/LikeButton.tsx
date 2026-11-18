import { useState } from 'react';
import { Heart } from 'lucide-react';

import { setLiked, type FeedItem } from '../api';

/** Like button shared by the feed cards and the post window. */
export default function LikeButton({ item, onChange }: { item: FeedItem; onChange: (item: FeedItem) => void }) {
  const [busy, setBusy] = useState(false);

  const toggle = async () => {
    if (busy) return;
    setBusy(true);
    // Optimistic: the heart reacts at once, the server's answer then sets the real count.
    const optimistic = {
      ...item,
      liked: !item.liked,
      like_count: item.like_count + (item.liked ? -1 : 1),
    };
    onChange(optimistic);
    try {
      onChange(await setLiked(item.id, optimistic.liked));
    } catch {
      onChange(item);
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        void toggle();
      }}
      aria-pressed={item.liked}
      title={item.liked ? 'Убрать лайк' : 'Нравится'}
      className={`flex items-center gap-1.5 px-2 py-1 border font-mono text-xs font-bold transition-colors ${
        item.liked
          ? 'border-orange-500 bg-orange-500/10 text-orange-500'
          : 'border-zinc-800 text-zinc-400 hover:border-orange-500 hover:text-orange-500'
      }`}
    >
      <Heart size={14} fill={item.liked ? 'currentColor' : 'none'} />
      {item.like_count}
    </button>
  );
}

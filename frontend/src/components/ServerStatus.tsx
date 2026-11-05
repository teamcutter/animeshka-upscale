import type { Health } from '../api';

const BACKEND_LABEL: Record<Health['backend'], string> = {
  realesrgan: 'Real-ESRGAN',
  stub: 'Stub (Lanczos)',
};

export default function ServerStatus({ health, unreachable }: { health: Health | null; unreachable: boolean }) {
  const down = unreachable || health?.status === 'degraded';
  const color = down ? 'bg-red-500' : health ? 'bg-emerald-500' : 'bg-stone-300';
  let text: string;
  if (unreachable) text = 'API недоступен';
  else if (!health) text = 'Подключение…';
  else if (health.status === 'degraded') text = `${BACKEND_LABEL[health.backend]} · БД недоступна`;
  else {
    const modes = Object.entries(health.modes)
      .filter(([, ok]) => ok)
      .map(([mode]) => mode)
      .join(', ');
    text = `${BACKEND_LABEL[health.backend]} · ${modes || 'нет моделей'}${health.auth === 'open' ? ' · вход отключён' : ''}`;
  }

  return (
    <div className="hidden sm:flex items-center space-x-2 text-xs text-orange-900/70" title="Состояние сервера">
      <span className={`w-2 h-2 rounded-full ${color}`} />
      <span>{text}</span>
    </div>
  );
}

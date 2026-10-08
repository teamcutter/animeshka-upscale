import type { Health } from '../api';

const BACKEND_LABEL: Record<Health['backend'], string> = {
  realesrgan: 'Real-ESRGAN',
  stub: 'Stub (Lanczos)',
};

export default function ServerStatus({
  health,
  unreachable,
}: {
  health: Health | null;
  unreachable: boolean;
}) {
  const down = unreachable || health?.status === 'degraded';
  const color = down ? 'bg-rose-500' : health ? 'bg-emerald-500' : 'bg-slate-300';
  const text = unreachable
    ? 'API недоступен'
    : !health
      ? 'Подключение…'
      : health.status === 'degraded'
        ? `${BACKEND_LABEL[health.backend]} · БД недоступна`
        : `${BACKEND_LABEL[health.backend]} · ${
            Object.entries(health.modes)
              .filter(([, ok]) => ok)
              .map(([mode]) => mode)
              .join(', ') || 'нет моделей'
          }`;

  return (
    <div className="hidden sm:flex items-center space-x-2 text-xs text-slate-500" title="Состояние сервера">
      <span className={`w-2 h-2 rounded-full ${color}`} />
      <span>{text}</span>
    </div>
  );
}

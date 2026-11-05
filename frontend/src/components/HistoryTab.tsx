export default function HistoryTab() {
  const mockHistory = [
    { id: 1, name: "my_art_final.png", status: "COMPLETED", date: "2026-11-05" },
    { id: 2, name: "photo_old_scan.jpg", status: "COMPLETED", date: "2026-11-04" },
    { id: 3, name: "video_render.mp4", status: "FAILED", date: "2026-11-03" },
  ];

  return (
    <div className="space-y-8">
      <div className="border-l-4 border-orange-500 pl-6 py-2">
        <h2 className="text-3xl font-black text-white uppercase tracking-tighter">Мои работы</h2>
        <p className="text-zinc-500 font-mono text-sm uppercase mt-1">USER_ARCHIVE</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {mockHistory.map((item) => (
          <div key={item.id} className="border border-zinc-800 bg-zinc-900 p-5 flex flex-col sm:flex-row sm:items-center justify-between group hover:border-orange-500 transition-colors gap-4">
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-zinc-950 border border-zinc-800 flex items-center justify-center text-zinc-500 font-mono text-xs shrink-0">
                {item.name.endsWith('.mp4') ? 'VID' : 'IMG'}
              </div>
              <div className="overflow-hidden">
                <h4 className="text-white font-bold truncate">{item.name}</h4>
                <div className="text-zinc-500 font-mono text-xs mt-1">{item.date}</div>
              </div>
            </div>
            
            <div className="flex items-center space-x-4 sm:ml-auto">
              <span className={`font-mono text-xs border px-2 py-1 ${
                item.status === 'COMPLETED' 
                  ? 'text-green-500 border-green-500/30 bg-green-500/10' 
                  : 'text-red-500 border-red-500/30 bg-red-500/10'
              }`}>
                {item.status}
              </span>
              <button className="text-orange-500 hover:text-white text-sm font-bold uppercase underline decoration-orange-500/50 underline-offset-4 disabled:opacity-50" disabled={item.status !== 'COMPLETED'}>
                Скачать
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
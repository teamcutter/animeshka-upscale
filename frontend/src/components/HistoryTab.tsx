export default function HistoryTab() {
  const mockHistory = [
    { id: 1, name: "anime_bg.png", date: "Сегодня, 14:30", preset: "x4 Anime", size: "4.2 MB" },
    { id: 2, name: "photo_test.jpg", date: "Вчера, 18:15", preset: "x2 Photo", size: "1.8 MB" },
    { id: 3, name: "texture_01.webp", date: "21 сент, 10:05", preset: "x4 Detail", size: "5.1 MB" },
  ];

  return (
    <div className="max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-slate-800 mb-6">История обработок</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {mockHistory.map((item) => (
          <div key={item.id} className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden group">
            {/* Заглушка для картинки */}
            <div className="h-48 bg-slate-100 flex items-center justify-center group-hover:bg-indigo-50 transition-colors">
              <span className="text-slate-400">Превью {item.name}</span>
            </div>
            <div className="p-4">
              <h3 className="font-semibold text-slate-800 truncate">{item.name}</h3>
              <div className="flex justify-between items-center mt-2 text-sm text-slate-500">
                <span>{item.date}</span>
                <span className="bg-indigo-50 text-indigo-600 px-2 py-1 rounded-md text-xs font-medium">
                  {item.preset}
                </span>
              </div>
              <div className="mt-4 flex space-x-2">
                <button className="flex-1 bg-indigo-50 text-indigo-600 py-2 rounded-lg text-sm font-medium hover:bg-indigo-100 transition-colors">
                  Скачать ({item.size})
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
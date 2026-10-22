export default function HistoryTab() {
  const mockHistory = [
    { id: 1, name: "anime_bg.png", date: "Сегодня, 14:30", preset: "x4 Anime", size: "4.2 MB" },
    { id: 2, name: "photo_test.jpg", date: "Вчера, 18:15", preset: "x2 Photo", size: "1.8 MB" },
  ];

  return (
    <div className="max-w-5xl mx-auto">
      {/* Плиточка под главный заголовок */}
      <div className="mb-6 inline-block bg-white/80 backdrop-blur-md px-6 py-3 rounded-2xl shadow-lg border border-orange-200/50">
        <h2 className="text-2xl font-bold text-stone-800">История обработок</h2>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {mockHistory.map((item) => (
          <div key={item.id} className="bg-white/80 backdrop-blur-md rounded-2xl shadow-lg border border-orange-200/50 overflow-hidden group flex flex-col">
            
            {/* Плиточка под текст внутри превью */}
            <div className="h-48 bg-orange-100/30 flex items-center justify-center group-hover:bg-orange-200/40 transition-colors border-b border-orange-100/50">
              <span className="text-stone-600 font-medium bg-white/70 backdrop-blur-sm px-4 py-2 rounded-xl shadow-sm border border-orange-100">
                Превью {item.name}
              </span>
            </div>
            
            <div className="p-5 flex-1 flex flex-col">
              <h3 className="font-bold text-stone-800 truncate">{item.name}</h3>
              <div className="flex justify-between items-center mt-2 text-sm text-stone-600">
                <span>{item.date}</span>
                <span className="bg-orange-100 text-orange-700 px-2 py-1 rounded-lg text-xs font-bold border border-orange-200/50">
                  {item.preset}
                </span>
              </div>
              <div className="mt-5 pt-4 border-t border-orange-100/50 mt-auto">
                <button className="w-full bg-orange-100 text-orange-700 py-2.5 rounded-xl text-sm font-bold hover:bg-orange-200 transition-colors shadow-sm">
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
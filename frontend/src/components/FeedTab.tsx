export default function FeedTab() {
  const mockFeed = [
    { id: 1, author: "Максим", image: "cyber_city_upscaled.png", preset: "x4_ANIME", date: "СЕГОДНЯ_15:30" },
    { id: 2, author: "AlexTheGreat", image: "sunset_vibes.jpg", preset: "x2_PHOTO", date: "ВЧЕРА_21:15" },
    { id: 3, author: "Ninja_88", image: "sketch_colored.png", preset: "x4_ANIME", date: "ВЧЕРА_18:40" },
  ];

  return (
    <div className="space-y-8">
      <div className="border-l-4 border-orange-500 pl-6 py-2">
        <h2 className="text-3xl font-black text-white uppercase tracking-tighter">Общая лента</h2>
        <p className="text-zinc-500 font-mono text-sm uppercase mt-1">PUBLISHED_WORKS</p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {mockFeed.map((item) => (
          <div key={item.id} className="border border-zinc-800 bg-zinc-900 flex flex-col group hover:border-orange-500 transition-colors">
            <div className="h-56 bg-zinc-950 flex items-center justify-center border-b border-zinc-800 relative overflow-hidden">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-zinc-800/20 to-transparent"></div>
              <span className="text-zinc-500 font-mono text-xs z-10 border border-zinc-800 bg-black px-3 py-1 truncate max-w-[80%]">
                {item.image}
              </span>
            </div>
            
            <div className="p-5 flex-1 flex flex-col">
              <div className="flex justify-between items-start mb-4">
                <h3 className="font-bold text-white text-lg truncate pr-2 uppercase tracking-wide">@{item.author}</h3>
                <span className="bg-orange-500/10 text-orange-500 border border-orange-500/50 px-2 py-1 text-xs font-mono font-bold whitespace-nowrap">
                  {item.preset}
                </span>
              </div>
              <div className="mt-auto pt-4 border-t border-zinc-800 flex justify-between items-center text-sm font-mono text-zinc-500">
                <span>{item.date}</span>
                <button className="text-orange-500 hover:text-white hover:bg-orange-500 px-3 py-1 border border-orange-500 transition-colors uppercase text-xs font-bold">
                  Открыть
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
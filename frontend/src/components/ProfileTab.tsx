export default function ProfileTab() {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex items-center space-x-6">
        <div className="w-24 h-24 bg-indigo-100 rounded-full flex items-center justify-center text-indigo-500 text-3xl font-bold">
          МВ
        </div>
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Максим Вибе</h2>
          <p className="text-slate-500">Студент • Pro Тариф</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
          <p className="text-slate-500 text-sm mb-1">Обработано изображений</p>
          <p className="text-3xl font-bold text-indigo-600">142</p>
        </div>
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
          <p className="text-slate-500 text-sm mb-1">Сэкономлено трафика</p>
          <p className="text-3xl font-bold text-teal-500">850 МБ</p>
        </div>
      </div>
      
      <button className="w-full py-3 mt-4 bg-rose-50 text-rose-600 rounded-xl font-medium hover:bg-rose-100 transition-colors">
        Выйти из аккаунта
      </button>
    </div>
  );
}
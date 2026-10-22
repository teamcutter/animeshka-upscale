export default function FallingLeaves() {
  // Единая форма резного листа
  const starLeafPath = "M17.5,3.62A8.53,8.53,0,0,0,12,12a8.5,8.5,0,0,0-5.5-8.38c-.37-.14-.73,0-1,.22s-.36.63-.3.94A10.89,10.89,0,0,0,10.59,12h0a1,1,0,0,1,0,2,10.9,10.9,0,0,0-5.41,7.22c-.06.31,0-.68.29-.94s.62.36,1,.22A8.53,8.53,0,0,0,12,14a8.5,8.5,0,0,0,5.5,8.38c.37.14.73,0,1-.22s.36-.63.3-.94A10.89,10.89,0,0,0,13.41,14h0a1,1,0,0,1,0-2,10.9,10.9,0,0,0,5.41-7.22c.06-.31,0-.68-.29-.94S17.87,3.48,17.5,3.62Z";

  // Распределение по левой и правой частям экрана с разной задержкой
  const leaves = [
    { id: 1, delay: "0s", pos: { left: "10%" }, color: "text-orange-500/60" },
    { id: 2, delay: "2s", pos: { right: "15%" }, color: "text-red-500/50" },
    { id: 3, delay: "4s", pos: { left: "25%" }, color: "text-orange-400/60" },
    { id: 4, delay: "6s", pos: { right: "35%" }, color: "text-yellow-600/50" },
    { id: 5, delay: "8s", pos: { left: "65%" }, color: "text-red-400/50" },
    { id: 6, delay: "10s", pos: { right: "75%" }, color: "text-orange-500/60" },
    { id: 7, delay: "12s", pos: { left: "85%" }, color: "text-yellow-500/50" },
    { id: 8, delay: "14s", pos: { right: "5%" }, color: "text-red-500/50" },
  ];

  return (
    <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
      {leaves.map((leaf) => (
        <svg 
          key={leaf.id} 
          className={`leaf w-7 h-7 ${leaf.color}`} 
          style={{ animationDelay: leaf.delay, ...leaf.pos }} 
          fill="currentColor" 
          viewBox="0 0 24 24"
        >
          <path d={starLeafPath} />
        </svg>
      ))}
    </div>
  );
}
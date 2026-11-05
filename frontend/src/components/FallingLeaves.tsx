import { useEffect, useState } from 'react';

export default function FallingLeaves() {
  const [leaves, setLeaves] = useState<any[]>([]);

  useEffect(() => {
    // Генерируем 15 случайных листиков
    const newLeaves = Array.from({ length: 15 }).map((_, i) => ({
      id: i,
      left: `${Math.random() * 100}%`,
      animationDuration: `${Math.random() * 10 + 10}s`, // от 10 до 20 секунд
      animationDelay: `${Math.random() * 10}s`,
      opacity: Math.random() * 0.4 + 0.2,
      size: `${Math.random() * 20 + 20}px`, // размер от 20 до 40px
      // Чередуем теплые осенние цвета
      color: ['#ea580c', '#c2410c', '#fb923c', '#d97706'][Math.floor(Math.random() * 4)]
    }));
    setLeaves(newLeaves);
  }, []);

  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
      {leaves.map((leaf) => (
        <div
          key={leaf.id}
          className="absolute top-[-50px] animate-fall"
          style={{
            left: leaf.left,
            animationDuration: leaf.animationDuration,
            animationDelay: leaf.animationDelay,
            opacity: leaf.opacity,
            width: leaf.size,
            height: leaf.size,
            color: leaf.color
          }}
        >
          {/* Исправленная форма листа */}
          <svg viewBox="0 0 256 256" fill="currentColor" xmlns="http://www.w3.org/2000/svg" style={{ filter: 'drop-shadow(0px 2px 4px rgba(0,0,0,0.3))' }}>
            <path d="M216,40c-2,28.56-22,79.78-53.86,111.65C136.14,177.65,99.42,196.44,55,197.86a8,8,0,0,1-7.63-3.95L33.66,207.58a8,8,0,0,1-11.32-11.31l13.67-13.68A8,8,0,0,1,32.07,175c1.43-44.4,20.22-81.12,46.22-107.11C110.15,36,161.4,16,216,16A24.05,24.05,0,0,1,240,40ZM146.68,140.79a8,8,0,1,0-11.32-11.31l32-32a8,8,0,0,0,11.32,11.31Z"/>
          </svg>
        </div>
      ))}
      <style>{`
        @keyframes fall {
          0% {
            transform: translateY(0) rotate(0deg) translateX(0);
          }
          25% {
            transform: translateY(25vh) rotate(90deg) translateX(20px);
          }
          50% {
            transform: translateY(50vh) rotate(180deg) translateX(-20px);
          }
          75% {
            transform: translateY(75vh) rotate(270deg) translateX(20px);
          }
          100% {
            transform: translateY(110vh) rotate(360deg) translateX(0);
          }
        }
        .animate-fall {
          animation-name: fall;
          animation-timing-function: linear;
          animation-iteration-count: infinite;
        }
      `}</style>
    </div>
  );
}
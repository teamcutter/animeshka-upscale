import { ReactCompareSlider, ReactCompareSliderImage } from 'react-compare-slider';

import type { FileInfo, MediaKind } from '../api';
import VideoComparison from './VideoComparison';

interface Props {
  kind: MediaKind;
  originalUrl: string;
  resultUrl: string;
  input: FileInfo;
  output: FileInfo | null;
  className?: string;
}

export default function MediaComparison({ kind, originalUrl, resultUrl, input, output, className = '' }: Props) {
  return (
    <div className={`relative bg-black ${className}`}>
      {kind === 'video' ? (
        <VideoComparison originalUrl={originalUrl} resultUrl={resultUrl} />
      ) : (
        <ReactCompareSlider
          itemOne={<ReactCompareSliderImage src={originalUrl} alt="До" style={{ objectFit: 'contain' }} />}
          itemTwo={<ReactCompareSliderImage src={resultUrl} alt="После" style={{ objectFit: 'contain' }} />}
          className="h-full w-full"
        />
      )}
      <span className="absolute top-3 left-3 bg-black/80 border border-zinc-700 px-2 py-0.5 font-mono text-[10px] text-zinc-300 pointer-events-none">
        ДО · {input.width}×{input.height}
      </span>
      <span className="absolute top-3 right-3 bg-orange-500 text-black px-2 py-0.5 font-mono text-[10px] font-bold pointer-events-none">
        ПОСЛЕ · {output?.width}×{output?.height}
      </span>
    </div>
  );
}

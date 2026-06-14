import { useEffect, useRef, useState } from 'react';
import { BboxOverlay } from '../components/BboxOverlay';

type Status = 'idle' | 'connecting' | 'running' | 'error';

interface FeedMessage {
  ts: number;
  jpeg_base64: string;
  objects: Record<string, unknown>[];
  scene: 'indoor' | 'outdoor' | 'unknown';
  danger: { is_danger: boolean; labels: string[] };
}

const SCENE_TEXT: Record<FeedMessage['scene'], string> = {
  indoor: '🏠 室内',
  outdoor: '🌳 室外',
  unknown: '❓ 未知',
};

export default function LivePreview() {
  const [status, setStatus] = useState<Status>('idle');
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<FeedMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  function start() {
    setStatus('connecting');
    setError(null);
    setMsg(null);
    const ws = new WebSocket('ws://localhost:8000/api/live/feed');
    wsRef.current = ws;

    ws.onopen = () => setStatus('running');
    ws.onmessage = (event) => {
      try {
        const data: FeedMessage = JSON.parse(event.data);
        setMsg(data);
      } catch {
        // 忽略坏帧
      }
    };
    ws.onerror = () => {
      setStatus('error');
      setError('WebSocket 连接失败，请确认后端正在运行');
    };
    ws.onclose = (event) => {
      if (event.code === 1008 && event.reason === 'ALREADY_RUNNING') {
        setStatus('error');
        setError('已有客户端在使用摄像头，请先关闭其他实时预览窗口');
      } else if (status === 'running') {
        setStatus('idle');
      }
    };
  }

  function stop() {
    wsRef.current?.close();
    wsRef.current = null;
    setStatus('idle');
    setMsg(null);
  }

  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">实时预览</h2>
        {status === 'idle' && (
          <button
            onClick={start}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white"
          >
            ⊕ 启动摄像头
          </button>
        )}
        {status === 'running' && (
          <button
            onClick={stop}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm text-white"
          >
            停止
          </button>
        )}
      </div>

      {status === 'idle' && !error && (
        <div className="rounded-xl bg-white p-8 text-center text-slate-500 shadow-sm">
          点击「启动摄像头」开始实时识别
        </div>
      )}

      {status === 'connecting' && (
        <div className="rounded-xl bg-white p-8 text-center text-slate-500 shadow-sm">
          正在连接摄像头……
        </div>
      )}

      {status === 'error' && (
        <div className="rounded-xl bg-red-50 p-6 text-sm text-red-700 shadow-sm">
          <p className="font-medium">出错了</p>
          <p className="mt-2">{error}</p>
          <button
            onClick={start}
            className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white"
          >
            重试
          </button>
        </div>
      )}

      {status === 'running' && msg && (
        <>
          <div className="relative inline-block w-full">
            <img
              src={`data:image/jpeg;base64,${msg.jpeg_base64}`}
              alt="实时摄像头画面"
              className="block w-full rounded-xl bg-black object-contain shadow-sm"
            />
            <BboxOverlay objects={msg.objects} />
          </div>

          <div className="flex flex-wrap gap-3 text-sm">
            <div className="rounded-full bg-slate-100 px-4 py-2">
              <span className="font-medium text-slate-900">场景：</span>
              <span className="ml-1">{SCENE_TEXT[msg.scene]}</span>
            </div>
            {msg.danger.is_danger ? (
              <div className="rounded-full bg-red-100 px-4 py-2 text-red-700">
                <span className="font-medium">⚠️ 危险：</span>
                <span className="ml-1">检测到「{msg.danger.labels.join('、')}」（无人机避障目标）</span>
              </div>
            ) : (
              <div className="rounded-full bg-green-100 px-4 py-2 text-green-700">
                ✅ 当前画面无危险目标
              </div>
            )}
          </div>

          <p className="text-xs text-slate-400">
            ⚡ 当前 CPU 推理约 5 FPS。切到 GPU 可达 30 FPS，详见 docs/CODEMAPS/yolo-gpu-migration.md
          </p>
        </>
      )}
    </section>
  );
}

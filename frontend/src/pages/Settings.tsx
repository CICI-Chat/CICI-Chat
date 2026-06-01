import { useEffect, useState } from 'react';
import { api, ReindexResult, Settings as SettingsType } from '../api/client';

export default function Settings() {
  const [settings, setSettings] = useState<SettingsType | null>(null);
  const [result, setResult] = useState<ReindexResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    api.getSettings().then(setSettings).catch((err: Error) => setError(err.message));
  }, []);

  async function reindex() {
    setScanning(true);
    setError(null);
    try {
      setResult(await api.reindex());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setScanning(false);
    }
  }

  if (error && !settings) return <p className="text-red-600">加载失败：{error}</p>;
  if (!settings) return <p>加载中……</p>;

  return (
    <section className="space-y-6">
      <h2 className="text-xl font-semibold">设置</h2>

      <div className="rounded-xl bg-white p-5 shadow-sm">
        <p className="text-sm text-slate-500">监听目录</p>
        <ul className="mt-2 list-disc pl-5 text-sm">{settings.watch_folders.map((folder) => <li key={folder}>{folder}</li>)}</ul>
        <p className="mt-4 text-sm text-slate-500">数据库：{settings.db_path}</p>
        <button disabled={scanning} onClick={reindex} className="mt-5 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">{scanning ? '扫描中……' : '重新扫描'}</button>
        {error && <p className="mt-4 text-sm text-red-600">扫描失败：{error}</p>}
        {result && <p className="mt-4 text-sm text-slate-600">新增 {result.added}，跳过 {result.skipped}，错误 {result.errors}</p>}
      </div>

      <div className="rounded-xl bg-white p-5 shadow-sm">
        <p className="text-sm text-slate-500">识别 Provider</p>
        <div className="mt-3 flex flex-col gap-3 rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
          <p><span className="font-medium text-slate-900">当前 Provider：</span>{settings.provider}</p>
          <p>当前阶段使用本地 Mock 识别，用于验证图片识别、结果持久化和批量流程。</p>
          <p>后续可将 Provider 替换为 Ollama 或云端视觉模型。</p>
          <p className="font-medium text-amber-700">Phase 3 不支持在页面切换 Provider。</p>
        </div>
      </div>
    </section>
  );
}

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
        <p className="mt-2 text-sm text-slate-500">Provider：{settings.provider}</p>
        <button disabled={scanning} onClick={reindex} className="mt-5 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">{scanning ? '扫描中……' : '重新扫描'}</button>
        {error && <p className="mt-4 text-sm text-red-600">扫描失败：{error}</p>}
        {result && <p className="mt-4 text-sm text-slate-600">新增 {result.added}，跳过 {result.skipped}，错误 {result.errors}</p>}
      </div>
    </section>
  );
}

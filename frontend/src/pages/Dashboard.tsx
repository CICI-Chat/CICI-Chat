import { useEffect, useState } from 'react';
import { api, Stats } from '../api/client';

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getStats().then(setStats).catch((err: Error) => setError(err.message));
  }, []);

  if (error) return <p className="text-red-600">加载失败：{error}</p>;
  if (!stats) return <p>加载中……</p>;

  return (
    <section className="space-y-6">
      <h2 className="text-xl font-semibold">统计看板</h2>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">图片总数</p><p className="mt-2 text-3xl font-bold">{stats.total_images}</p></div>
        <div className="rounded-xl bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">标签种类</p><p className="mt-2 text-3xl font-bold">{Object.keys(stats.tags).length}</p></div>
        <div className="rounded-xl bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">格式种类</p><p className="mt-2 text-3xl font-bold">{Object.keys(stats.formats).length}</p></div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl bg-white p-5 shadow-sm"><h3 className="font-semibold">标签 Top</h3>{Object.entries(stats.tags).map(([name, count]) => <p key={name} className="mt-2 flex justify-between text-sm"><span>{name}</span><span>{count}</span></p>)}</div>
        <div className="rounded-xl bg-white p-5 shadow-sm"><h3 className="font-semibold">格式分布</h3>{Object.entries(stats.formats).map(([name, count]) => <p key={name} className="mt-2 flex justify-between text-sm"><span>{name}</span><span>{count}</span></p>)}</div>
      </div>
    </section>
  );
}

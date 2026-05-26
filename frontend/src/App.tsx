import { useState } from 'react';
import Dashboard from './pages/Dashboard';
import Gallery from './pages/Gallery';
import ImageDetail from './pages/ImageDetail';
import Settings from './pages/Settings';

type Page = 'gallery' | 'dashboard' | 'settings';

export default function App() {
  const [page, setPage] = useState<Page>('gallery');
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);

  if (selectedImageId) {
    return <ImageDetail imageId={selectedImageId} onBack={() => setSelectedImageId(null)} />;
  }

  return (
    <div className="min-h-screen">
      <header className="border-b bg-white px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">PicMind</h1>
            <p className="text-sm text-slate-500">本地图片智能管理系统</p>
          </div>
          <nav className="flex gap-2">
            {(['gallery', 'dashboard', 'settings'] as Page[]).map((item) => (
              <button
                key={item}
                onClick={() => setPage(item)}
                className={`rounded-lg px-4 py-2 text-sm ${page === item ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700'}`}
              >
                {item === 'gallery' ? '图库' : item === 'dashboard' ? '看板' : '设置'}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        {page === 'gallery' && <Gallery onSelectImage={setSelectedImageId} />}
        {page === 'dashboard' && <Dashboard />}
        {page === 'settings' && <Settings />}
      </main>
    </div>
  );
}

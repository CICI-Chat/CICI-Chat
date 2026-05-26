import { useEffect, useState } from 'react';
import { api, ImageItem } from '../api/client';

export default function Gallery({ onSelectImage }: { onSelectImage: (id: string) => void }) {
  const [images, setImages] = useState<ImageItem[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listImages()
      .then((data) => {
        setImages(data.items);
        setTotal(data.total);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) return <p className="text-red-600">加载失败：{error}</p>;

  return (
    <section>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h2 className="text-xl font-semibold">图库</h2>
          <p className="text-sm text-slate-500">共 {total} 张图片</p>
        </div>
      </div>
      {images.length === 0 ? (
        <div className="rounded-xl border border-dashed bg-white p-10 text-center text-slate-500">暂无图片，请在设置的目录中添加图片后重新扫描。</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {images.map((image) => (
            <button key={image.id} onClick={() => onSelectImage(image.id)} className="overflow-hidden rounded-xl bg-white text-left shadow-sm transition hover:shadow-md">
              <img src={image.image_url} alt={image.caption} className="h-44 w-full object-cover" />
              <div className="p-3">
                <p className="line-clamp-2 text-sm font-medium">{image.caption}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {image.tags.map((tag) => (
                    <span key={tag} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">{tag}</span>
                  ))}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

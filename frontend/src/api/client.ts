export type ImageItem = {
  id: string;
  file_path: string;
  file_size: number;
  width: number;
  height: number;
  format: string;
  created_at: string;
  modified_at: string;
  indexed_at: string;
  caption: string;
  tags: string[];
  image_url: string;
};

export type ImageDetail = ImageItem & {
  objects: Record<string, unknown>[];
  model_used: string;
};

export type ImageList = {
  items: ImageItem[];
  total: number;
  page: number;
  size: number;
};

export type ImageListParams = {
  page?: number;
  size?: number;
  q?: string;
  tag?: string;
  format?: string;
  sort?: 'indexed_at' | 'modified_at' | 'file_size' | 'width' | 'height';
  order?: 'asc' | 'desc';
};

export type Stats = {
  total_images: number;
  tags: Record<string, number>;
  formats: Record<string, number>;
};

export type Settings = {
  watch_folders: string[];
  db_path: string;
  provider: string;
};

export type ReindexResult = {
  added: number;
  skipped: number;
  errors: number;
};

export type RecognitionBatch = {
  batch_id: string;
  total: number;
  completed: number;
  failed: number;
  pending: number;
  running: number;
  status: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listImages: (params: ImageListParams = {}) => {
    const searchParams = new URLSearchParams({
      page: String(params.page ?? 1),
      size: String(params.size ?? 50),
    });
    if (params.q) searchParams.set('q', params.q);
    if (params.tag) searchParams.set('tag', params.tag);
    if (params.format) searchParams.set('format', params.format);
    if (params.sort) searchParams.set('sort', params.sort);
    if (params.order) searchParams.set('order', params.order);
    return request<ImageList>(`/api/images?${searchParams}`);
  },
  getImage: (id: string) => request<ImageDetail>(`/api/images/${encodeURIComponent(id)}`),
  recognizeImage: (id: string) =>
    request<ImageDetail>(`/api/images/${encodeURIComponent(id)}/recognize`, { method: 'POST' }),
  createRecognitionBatch: (imageIds: string[]) =>
    request<RecognitionBatch>('/api/recognition/batches', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_ids: imageIds }),
    }),
  getRecognitionBatch: (batchId: string) =>
    request<RecognitionBatch>(`/api/recognition/batches/${encodeURIComponent(batchId)}`),
  getStats: () => request<Stats>('/api/stats'),
  getSettings: () => request<Settings>('/api/settings'),
  reindex: () => request<ReindexResult>('/api/reindex', { method: 'POST' }),
};

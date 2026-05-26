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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listImages: (page = 1, size = 50, tag?: string) => {
    const params = new URLSearchParams({ page: String(page), size: String(size) });
    if (tag) params.set('tag', tag);
    return request<ImageList>(`/api/images?${params}`);
  },
  getImage: (id: string) => request<ImageDetail>(`/api/images/${encodeURIComponent(id)}`),
  getStats: () => request<Stats>('/api/stats'),
  getSettings: () => request<Settings>('/api/settings'),
  reindex: () => request<ReindexResult>('/api/reindex', { method: 'POST' }),
};

const DEFAULT_BASE =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${DEFAULT_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  generatePost: (body: Record<string, unknown>) =>
    request("/dashboard/generate-post", { method: "POST", body: JSON.stringify(body) }),

  keywordPost: (body: Record<string, unknown>) =>
    request("/dashboard/keyword-post", { method: "POST", body: JSON.stringify(body) }),

  auditPost: (body: Record<string, unknown>) =>
    request("/dashboard/audit-post", { method: "POST", body: JSON.stringify(body) }),

  seo: (body: Record<string, unknown>) =>
    request("/dashboard/seo", { method: "POST", body: JSON.stringify(body) }),

  listPosts: () => request<{ count: number; items: SavedPost[] }>("/dashboard/posts"),

  savePost: (body: Record<string, unknown>) =>
    request("/dashboard/posts/save", { method: "POST", body: JSON.stringify(body) }),

  updateStatus: (id: number, status: string) =>
    request(`/dashboard/posts/${id}/status`, {
      method: "PUT",
      body: JSON.stringify({ status }),
    }),

  deletePost: (id: number) =>
    request(`/dashboard/posts/${id}`, { method: "DELETE" }),
};

export type SavedPost = {
  id: number;
  content_type: string;
  raw_input: unknown;
  generated_output: unknown;
  source_grade?: string;
  keywords?: string;
  seo_keywords?: string;
  region?: string;
  category?: string;
  audit_score?: number;
  status: string;
  created_at?: string;
};

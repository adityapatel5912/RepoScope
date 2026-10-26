export async function fetchHealth(): Promise<Response> {
  return fetch("/api/health");
}

export async function createItem(id: string): Promise<Response> {
  return fetch(`/api/items/${id}`, { method: "POST" });
}

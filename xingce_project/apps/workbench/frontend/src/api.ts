export type Data = Record<string, any>;
export async function api(path: string, body?: Data): Promise<Data> {
  const response = await fetch(`/api${path}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    let detail = "";
    try {
      const data = await response.json();
      detail =
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail);
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || `请求失败（${response.status}）`);
  }
  return response.json();
}
export const list = (value: any): Data[] => (Array.isArray(value) ? value : []);

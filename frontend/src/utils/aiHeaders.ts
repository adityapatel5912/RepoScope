/**
 * aiHeaders.ts
 * Read AI provider BYOK credentials from sessionStorage and format them
 * into HTTP request headers.
 */
export function aiHeaders(): Record<string, string> {
  const provider = sessionStorage.getItem('rs-ai-provider');
  const key = sessionStorage.getItem('rs-ai-key');
  const model = sessionStorage.getItem('rs-ai-model');
  const baseUrl = sessionStorage.getItem('rs-ai-base-url');
  const headers: Record<string, string> = {};
  if (provider) headers['X-AI-Provider'] = provider;
  if (key) headers['X-AI-Key'] = key;
  if (model) headers['X-AI-Model'] = model;
  if (baseUrl) headers['X-AI-Base-Url'] = baseUrl;
  return headers;
}

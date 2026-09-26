/**
 * sse.ts — Hardened SSE parser.
 * Handles multi-line data blocks, comments, heartbeat pings, and \r\n line endings.
 */

export interface SSEEvent {
  event: string;
  data: string;
}

export async function* parseSSE(
  reader: ReadableStreamDefaultReader<Uint8Array>
): AsyncGenerator<SSEEvent> {
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Split on blank lines (SSE event boundaries); handle \r\n and \n
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() ?? "";

    for (const block of parts) {
      if (!block.trim()) continue;
      const lines = block.split(/\r?\n/);
      let event = "message";
      const dataLines: string[] = [];

      for (const line of lines) {
        if (line.startsWith(":")) continue;          // comment / heartbeat
        if (line.startsWith("event:")) {
          event = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trim());
        }
        // id: and retry: fields are intentionally ignored
      }

      if (dataLines.length === 0) continue;
      yield { event, data: dataLines.join("\n") };
    }
  }
}

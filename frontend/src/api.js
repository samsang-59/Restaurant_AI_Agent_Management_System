export async function fetchMenu() {
  const res = await fetch("/api/menu");
  if (!res.ok) throw new Error(`Menu request failed (${res.status})`);
  return res.json();
}

export async function newSession() {
  const res = await fetch("/api/session", { method: "POST" });
  if (!res.ok) throw new Error(`Session request failed (${res.status})`);
  return (await res.json()).session_id;
}

/** POST a guest message and invoke onEvent for every Server-Sent Event the agent streams back. */
export async function sendMessage(sessionId, message, onEvent) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Chat request failed (${res.status})`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      if (chunk.startsWith("data: ")) onEvent(JSON.parse(chunk.slice(6)));
    }
  }
}

Step 1F: Frontend — Update api.ts
Add these functions to frontend/src/app/api.ts:
typescript// ── Conversations API ──────────────────────────────────────────────────────

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationMessage {
  id: string;
  question: string;
  answer: string;
  sourcesUsed: string[];
  createdAt: string;
}

export async function createConversation(title = 'New Chat'): Promise<Conversation> {
  const res = await fetch(`${API_BASE}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error('Failed to create conversation');
  return res.json();
}

export async function fetchConversations(): Promise<Conversation[]> {
  const res = await fetch(`${API_BASE}/conversations`);
  if (!res.ok) throw new Error('Failed to fetch conversations');
  const data = await res.json();
  return data.conversations ?? [];
}

export async function fetchConversationMessages(convId: string): Promise<{
  conversation: { id: string; title: string };
  messages: ConversationMessage[];
}> {
  const res = await fetch(`${API_BASE}/conversations/${convId}/messages`);
  if (!res.ok) throw new Error('Failed to fetch messages');
  return res.json();
}

export async function renameConversation(convId: string, title: string): Promise<void> {
  await fetch(`${API_BASE}/conversations/${convId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
}

export async function deleteConversation(convId: string): Promise<void> {
  await fetch(`${API_BASE}/conversations/${convId}`, { method: 'DELETE' });
}
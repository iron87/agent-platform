import type { ConversationItem } from "./types";

const STORAGE_KEY = "two-brain.web-console.conversations.v1";

interface StoredConversations {
  items: ConversationItem[];
}

function emptyStore(): StoredConversations {
  return { items: [] };
}

export function loadConversations(): StoredConversations {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return emptyStore();
  }

  try {
    const parsed = JSON.parse(raw) as StoredConversations;
    if (!parsed || !Array.isArray(parsed.items)) {
      return emptyStore();
    }
    return parsed;
  } catch {
    return emptyStore();
  }
}

export function saveConversations(store: StoredConversations): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

export function upsertConversation(item: ConversationItem): void {
  const current = loadConversations();
  const exists = current.items.some((conv) => conv.id === item.id);
  const nextItems = exists
    ? current.items.map((conv) => (conv.id === item.id ? item : conv))
    : [item, ...current.items];
  saveConversations({ items: nextItems });
}

export function listConversationsByProfile(profileId: string): ConversationItem[] {
  const current = loadConversations();
  return current.items
    .filter((item) => item.profileId === profileId)
    .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt));
}

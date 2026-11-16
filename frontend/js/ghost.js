import { GHOST_WORDS } from "./ghost-words.js";

const WORD_SET = new Set(GHOST_WORDS);
const MIN_PREFIX = 2;
const MAX_PREFIX = 24;

const PHRASES = [
  ["on the other hand", ", "],
  ["as a result", ", "],
  ["for example", ","],
  ["for instance", ","],
  ["in addition", ", "],
  ["in conclusion", ", "],
  ["in other words", ", "],
  ["due to the fact", " that"],
  ["looking forward", " to"],
  ["thank you", " for"],
  ["according", " to"],
  ["please let me", " know"],
  ["i would like", " to"],
  ["we would like", " to"],
  ["it is important", " to"],
  ["in order", " to"],
  ["as soon", " as"],
  ["i think", " that"],
  ["we believe", " that"],
  ["in my opinion", ", "],
  ["first of all", ", "],
  ["more importantly", ", "],
  ["however", ", "],
  ["therefore", ", "],
  ["furthermore", ", "],
  ["moreover", ", "],
  ["meanwhile", ", "],
  ["nevertheless", ", "],
  ["consequently", ", "],
].sort((a, b) => b[0].length - a[0].length);

function phraseCompletion(text) {
  const lower = text.toLowerCase();
  for (const [trigger, insertion] of PHRASES) {
    if (!lower.endsWith(trigger)) continue;
    const start = lower.length - trigger.length;
    if (start > 0 && /[a-z'-]/.test(lower[start - 1])) continue;
    return insertion;
  }
  return "";
}

function documentWords(text) {
  const counts = new Map();
  for (const match of text.matchAll(/[A-Za-z][A-Za-z'-]{2,23}/g)) {
    const word = match[0].toLowerCase();
    counts.set(word, (counts.get(word) || 0) + 1);
  }
  return [...counts.entries()]
    .filter(([word]) => word.length >= MIN_PREFIX)
    .sort((a, b) => b[1] - a[1])
    .map(([word]) => word);
}

function wordCompletion(text, partial) {
  const lower = partial.toLowerCase();
  if (lower.length < MIN_PREFIX || lower.length > MAX_PREFIX) return "";
  if (lower.includes("'")) return "";
  if (WORD_SET.has(lower)) return "";

  const prefix = text.slice(0, -partial.length);
  const candidates = [...documentWords(prefix), ...GHOST_WORDS];
  for (const candidate of candidates) {
    if (candidate.length <= partial.length) continue;
    if (!candidate.startsWith(lower)) continue;
    if (candidate.length > partial.length + 20) continue;
    return applyCase(partial, candidate.slice(partial.length));
  }
  return "";
}

function applyCase(partial, remainder) {
  if (partial.length > 1 && partial === partial.toUpperCase()) return remainder.toUpperCase();
  return remainder;
}

export function completeText(text) {
  if (!text || text.length === 0) return "";
  const match = text.match(/([A-Za-z][A-Za-z'-]*)$/);
  if (match) {
    const phrase = phraseCompletion(text);
    if (phrase) return phrase;
    return wordCompletion(text, match[1]);
  }
  return phraseCompletion(text);
}

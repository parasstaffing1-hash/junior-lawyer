/**
 * Display helpers for values that arrive from the API in machine form.
 *
 * Several workspaces already carry a local `nice()` with the same body; this
 * is the shared version for new call sites, so the next one does not become
 * the tenth copy.
 */

/** "on_hold" -> "On hold". Enum values are never shown raw. */
export function formatEnum(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

/** "1 document" / "2 documents" — the count reads as a sentence, not a field. */
export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

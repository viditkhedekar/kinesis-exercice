// Tiny in-memory handoff so a file dropped on the dashboard can be picked up by
// the upload page after navigation (Files can't be passed via the URL).
let pending: File | null = null;

export function setPendingFile(f: File | null) {
  pending = f;
}
export function takePendingFile(): File | null {
  const f = pending;
  pending = null;
  return f;
}

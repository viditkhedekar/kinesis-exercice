// Shared, lightweight email validation — mirrors the backend regex so the client
// can give immediate feedback before a request is ever made.
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;

export function isValidEmail(email: string): boolean {
  const e = email.trim();
  return e.length > 0 && e.length <= 254 && EMAIL_RE.test(e);
}

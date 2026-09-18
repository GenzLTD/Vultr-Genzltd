/**
 * Validation utilities shared across brands.
 */

export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function isPasswordStrong(password: string): boolean {
  return password.length >= 8;
}

export function isNotEmpty(value?: string | null): boolean {
  return value !== undefined && value !== null && value.trim().length > 0;
}

export function isValidPhone(phone: string): boolean {
  return /^1[3-9]\d{9}$/.test(phone);
}

export function isValidUrl(url: string): boolean {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

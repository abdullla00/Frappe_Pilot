import { FrappeApp } from 'frappe-js-sdk';

const frappeUrl = import.meta.env.VITE_FRAPPE_URL || window.location.origin;

export const frappe = new FrappeApp(frappeUrl);

export const auth = frappe.auth();
export const db = frappe.db();
export const call = frappe.call();

export function getCsrfToken(): string {
  return window.csrf_token || '';
}

export function getCurrentUser(): string {
  const bootUser = window.frappe?.boot?.user;
  if (typeof bootUser === 'object' && bootUser !== null) {
    return bootUser.name || '';
  }
  if (typeof bootUser === 'string') {
    return bootUser;
  }
  return '';
}

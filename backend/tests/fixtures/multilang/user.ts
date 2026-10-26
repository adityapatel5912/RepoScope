// Fixture: TypeScript module.
// Imports the sibling TypeScript module to exercise TS relative resolution.
import { formatName } from './format';

export interface User {
  id: string;
  name: string;
}

export function displayName(user: User): string {
  return formatName(user.name);
}

export const DEFAULT_USER: User = { id: '0', name: 'anonymous' };

export async function loadUser(id: string): Promise<User> {
  return { id, name: `user-${id}` };
}

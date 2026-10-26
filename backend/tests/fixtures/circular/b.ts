// Fixture: second module in a TypeScript circular import chain.
import { cValue } from './c';

export function bValue(): number {
  return cValue() + 1;
}

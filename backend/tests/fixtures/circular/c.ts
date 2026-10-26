// Fixture: third module in a TypeScript circular import chain.
import { aValue } from './a';

export function cValue(): number {
  return aValue() + 1;
}

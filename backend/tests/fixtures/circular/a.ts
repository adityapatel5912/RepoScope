// Fixture: first module in a TypeScript circular import chain.
import { bValue } from './b';

export function aValue(): number {
  return bValue() + 1;
}

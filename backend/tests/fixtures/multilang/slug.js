// Fixture: JavaScript module (CommonJS-free ESM).
import { formatName } from './format';

export function slugify(input) {
  return formatName(input).toLowerCase().replace(/\s+/g, '-');
}

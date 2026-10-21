// Fixture: TSX module.
// Imports both the TS module and the TSX sibling.
import { formatName } from './format';
import { Button } from './Button';

export function renderLabel(text: string): string {
  return formatName(text);
}

export function Card(): JSX.Element {
  return <Button label="ok" />;
}

/**
 * logger.ts
 * Dev-only debug logging. Production builds strip log() entirely;
 * console.error stays available for real errors.
 */
export const log: (...args: unknown[]) => void = import.meta.env.DEV
  ? console.log.bind(console)
  : () => {};

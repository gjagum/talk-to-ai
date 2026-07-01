import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * cn — shadcn/ui's standard className combiner: clsx for conditionals +
 * tailwind-merge to dedupe conflicting Tailwind classes (last one wins).
 *
 * Usage:  cn('p-2', isActive && 'bg-blue-600', 'p-4')  →  'bg-blue-600 p-4'
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

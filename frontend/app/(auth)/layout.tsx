import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'Prism — Sign in' };

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

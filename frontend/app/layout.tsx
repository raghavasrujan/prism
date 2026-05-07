import type { Metadata } from 'next';
import './globals.css';
import { Providers } from '@/components/providers';

export const metadata: Metadata = {
  title: 'Prism',
  description: 'Prism — many models refracted through one lens.',
  robots: { index: false, follow: false },
};

// Anti-flicker script: apply theme BEFORE React hydrates so there's no flash
const themeScript = `
(function(){
  try {
    var stored = JSON.parse(localStorage.getItem('prism-theme') || '{}');
    var theme = stored.state && stored.state.theme ? stored.state.theme : 'light';
    document.documentElement.setAttribute('data-theme', theme);
  } catch(e) {
    document.documentElement.setAttribute('data-theme', 'light');
  }
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Anti-flicker theme init */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        {/* Fonts — raw <link> (not next/font) so the page still renders on the
            system-font fallback chain in --font-serif/--font-sans/--font-mono
            if the Google Fonts request fails in a restricted network. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=EB+Garamond:ital,wght@0,400;0,500;1,400&family=Inter:ital,wght@0,400;0,500;0,600;0,700;1,400&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}



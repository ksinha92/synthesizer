'use client';

import type { IconConfig } from '@/components/blocks/modern-animated-sign-in';

/**
 * Orbit array for the sign-in page. Real vendor logos served from
 * jsdelivr's devicon/simple-icons mirrors. The CSP rule in next.config.js
 * whitelists `https://cdn.jsdelivr.net` under img-src.
 *
 * Layout mirrors the demo's spacing — inner ring r=100, middle r=150/210,
 * outer r=270/320 — so the animation visually matches the reference but
 * with Synthia's actual data-source connectors.
 */
const devicon = (slug: string, variant = 'original') =>
  `https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/${slug}/${slug}-${variant}.svg`;

const simpleIcon = (slug: string) =>
  `https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/${slug}.svg`;

function VendorIcon({ src, alt }: { src: string; alt: string }) {
  // Plain <img> on purpose — these are tiny SVGs from a CDN; we don't need
  // next/image optimization and avoiding it keeps the CSP simple.
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt={alt} width={100} height={100} draggable={false} />;
}

// One icon per radius gets `path: true` so the OrbitingCircles SVG renders the
// faint guide-circle once per ring (drawing it for every icon at the same
// radius would stack identical strokes and visually thicken the line).
export const dbIconsArray: IconConfig[] = [
  // --- Inner ring (radius 100) ---
  {
    component: () => (
      <VendorIcon src={devicon('postgresql')} alt='PostgreSQL' />
    ),
    className: 'size-[30px] border-none bg-transparent',
    duration: 20,
    delay: 20,
    radius: 100,
    path: true,
    reverse: false,
  },
  {
    component: () => <VendorIcon src={devicon('mysql')} alt='MySQL' />,
    className: 'size-[30px] border-none bg-transparent',
    duration: 20,
    delay: 10,
    radius: 100,
    path: false,
    reverse: false,
  },

  // --- Inner-reverse ring (radius 150) ---
  {
    component: () => <VendorIcon src={devicon('mongodb')} alt='MongoDB' />,
    className: 'size-[30px] border-none bg-transparent',
    duration: 20,
    delay: 20,
    radius: 150,
    path: true,
    reverse: true,
  },
  {
    component: () => <VendorIcon src={devicon('redis')} alt='Redis' />,
    className: 'size-[30px] border-none bg-transparent',
    duration: 20,
    delay: 10,
    radius: 150,
    path: false,
    reverse: true,
  },

  // --- Middle ring (radius 210) ---
  {
    component: () => (
      <VendorIcon
        src={devicon('microsoftsqlserver', 'plain')}
        alt='SQL Server'
      />
    ),
    className: 'size-[50px] border-none bg-transparent',
    radius: 210,
    duration: 20,
    path: true,
    reverse: false,
  },
  {
    component: () => <VendorIcon src={devicon('oracle')} alt='Oracle' />,
    className: 'size-[50px] border-none bg-transparent',
    radius: 210,
    duration: 20,
    delay: 20,
    path: false,
    reverse: false,
  },

  // --- Outer-reverse ring (radius 270) ---
  {
    component: () => (
      <VendorIcon src={simpleIcon('snowflake')} alt='Snowflake' />
    ),
    className: 'size-[50px] border-none bg-transparent',
    radius: 270,
    duration: 20,
    path: true,
    reverse: true,
  },
  {
    component: () => (
      <VendorIcon src={simpleIcon('databricks')} alt='Databricks' />
    ),
    className: 'size-[50px] border-none bg-transparent',
    radius: 270,
    duration: 20,
    delay: 60,
    path: false,
    reverse: true,
  },

  // --- Far outer ring (radius 320) ---
  {
    component: () => (
      <VendorIcon
        src={devicon('googlecloud')}
        alt='Google Cloud / BigQuery'
      />
    ),
    className: 'size-[50px] border-none bg-transparent',
    radius: 320,
    duration: 20,
    delay: 20,
    path: true,
    reverse: false,
  },
  {
    component: () => (
      <VendorIcon src={devicon('amazonwebservices', 'plain-wordmark')} alt='AWS S3' />
    ),
    className: 'size-[50px] border-none bg-transparent',
    radius: 320,
    duration: 20,
    delay: 5,
    path: false,
    reverse: false,
  },
];

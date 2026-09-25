/**
 * Per-route <head> metadata on client-side navigation.
 *
 * The FIRST load of any URL is already fully server-rendered by backend/app/seo.py (title,
 * description, canonical, hreflang, Open Graph, Twitter card, JSON-LD and a crawler summary
 * of the live data). Crawlers only ever see that. This hook keeps the tags correct for the
 * person who then navigates inside the SPA (browser tab title, share sheets, "copy link").
 *
 * It reads the route map the server embeds in the page (<script type="application/json"
 * id="seo-routes">) so titles and descriptions have ONE source of truth: ROUTES in seo.py.
 * With no server (Vite dev server) it falls back to the site name.
 *
 *   useSeo()                                   // Layout: metadata of the current path
 *   useSeo({ title, description, path })       // a page with its own text (Learn topic)
 *   useSeo({ noindex: true })                  // a page that must not be indexed
 *   useSeo({ jsonLd: {...} })                  // replace the JSON-LD for this view
 */
import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

export interface SeoInput {
  /** Full document title (no site-name suffix is added; keep it <= 60 chars). */
  title?: string
  /** 140-160 chars ideally. */
  description?: string
  /** Canonical path; defaults to the current location.pathname (no query, no hash). */
  path?: string
  /** A schema.org object (or @graph) for this view; null/undefined keeps a minimal WebPage. */
  jsonLd?: Record<string, unknown> | null
  noindex?: boolean
}

export interface SeoRouteMap {
  origin: string
  site_name: string
  og_image: string
  routes: Record<string, { title: string; description: string }>
}

let cached: SeoRouteMap | null | undefined

/** The route map embedded by the server, or null on the dev server. */
export function seoRouteMap(): SeoRouteMap | null {
  if (cached !== undefined) return cached
  try {
    const el = document.getElementById('seo-routes')
    cached = el?.textContent ? (JSON.parse(el.textContent) as SeoRouteMap) : null
  } catch {
    cached = null
  }
  return cached
}

const DEFAULT_ROBOTS = 'index,follow,max-image-preview:large'

function upsert<K extends keyof HTMLElementTagNameMap>(
  selector: string, tag: K, attrs: Record<string, string>,
): HTMLElementTagNameMap[K] {
  let el = document.head.querySelector<HTMLElementTagNameMap[K]>(selector)
  if (!el) {
    el = document.createElement(tag)
    document.head.appendChild(el)
  }
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v)
  return el
}

const meta = (attr: 'name' | 'property', key: string, content: string) =>
  upsert(`meta[${attr}="${key}"]`, 'meta', { [attr]: key, content })

/** Metadata for a path from the server map (exact, then without trailing slash). */
export function seoFor(path: string): { title: string; description: string } | null {
  const map = seoRouteMap()
  if (!map) return null
  return map.routes[path] ?? map.routes[path.replace(/\/+$/, '') || '/'] ?? null
}

export function useSeo(input: SeoInput = {}): void {
  const loc = useLocation()
  const path = input.path ?? loc.pathname
  const jsonLdKey = input.jsonLd ? JSON.stringify(input.jsonLd) : ''

  useEffect(() => {
    const map = seoRouteMap()
    const base = seoFor(path)
    const siteName = map?.site_name ?? 'El Nino Watch'
    const title = input.title ?? base?.title ?? siteName
    const description = input.description ?? base?.description ?? ''
    const origin = map?.origin ?? window.location.origin
    const url = origin + path

    document.title = title
    meta('name', 'description', description)
    meta('name', 'robots', input.noindex ? 'noindex,follow' : DEFAULT_ROBOTS)
    meta('property', 'og:title', title)
    meta('property', 'og:description', description)
    meta('property', 'og:url', url)
    meta('property', 'og:site_name', siteName)
    meta('name', 'twitter:title', title)
    meta('name', 'twitter:description', description)
    if (map?.og_image) {
      meta('property', 'og:image', map.og_image)
      meta('name', 'twitter:image', map.og_image)
    }
    upsert('link[rel="canonical"]', 'link', { rel: 'canonical', href: url })
    upsert('link[rel="alternate"][hreflang="en"]', 'link', { rel: 'alternate', hreflang: 'en', href: url })
    upsert('link[rel="alternate"][hreflang="x-default"]', 'link', { rel: 'alternate', hreflang: 'x-default', href: url })

    // JSON-LD: the server's block describes the server-rendered path only. On another
    // path, replace it with what the page provides, else a minimal WebPage.
    const ld = document.head.querySelector<HTMLScriptElement>('script[type="application/ld+json"]')
    const serverPath = ld?.dataset.path
    if (input.jsonLd || (ld && serverPath !== path) || !ld) {
      const data = input.jsonLd ?? {
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: title,
        description,
        url,
        inLanguage: 'en',
        isPartOf: { '@id': `${origin}/#website` },
      }
      const el = ld ?? document.createElement('script')
      el.type = 'application/ld+json'
      el.dataset.path = path
      el.textContent = JSON.stringify(data)
      if (!ld) document.head.appendChild(el)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, input.title, input.description, input.noindex, jsonLdKey])
}

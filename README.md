# Reviwo

Embeddable Yelp reviews carousel widget. Drop a snippet on any site to show live reviews for a Yelp business.

**Live demo:** [reviwo-pi.vercel.app](https://reviwo-pi.vercel.app/reviwo-widget.html)

## Embed code

Paste this into your site (HTML block, footer, or page builder):

```html
<script src="https://reviwo-pi.vercel.app/embed.js" async></script>
<div class="mdg-yelp-widget"
     data-yelp="https://www.yelp.com/biz/YOUR-BUSINESS"
     data-height="480"></div>
```

Replace `YOUR-BUSINESS` with the slug from the Yelp business URL (everything after `/biz/`).

The widget always embeds **up to 3 reviews** for the business in `data-yelp`.

### Optional attributes

| Attribute | Description | Default |
|-----------|-------------|---------|
| `data-yelp` | Full Yelp business URL (**required**) | — |
| `data-height` | Initial iframe height in pixels | `480` |
| `data-header-color` | Header background (hex, rgb, hsl) | `#fff` |
| `data-card-color` | Review card background | `#fff` |

### Example with custom colors

```html
<script src="https://reviwo-pi.vercel.app/embed.js" async></script>
<div class="mdg-yelp-widget"
     data-yelp="https://www.yelp.com/biz/mobile-dog-grooming-irvine-2"
     data-height="520"
     data-header-color="#ffffff"
     data-card-color="#f5f5f5"></div>
```

## Yelp API plans

Set `YELP_API_KEY` so any `data-yelp` URL can resolve.

| Plan / API | Reviews in Reviwo |
|------------|-------------------|
| Places **Enhanced** (or higher) | Official Fusion Reviews API — up to **3** excerpts |
| Places **Base** | Business lookup works; review excerpts are **not** included on Base ([plans](https://docs.developer.yelp.com/docs/plans)). Reviwo falls back to the public review feed when possible. |
| [Private Reviews API](https://docs.developer.yelp.com/docs/private-reviews-api) | Partner-only (disabled by default). Tried automatically when your key has access. |

If changing `data-yelp` fails, check that the URL contains `/biz/…` and that `YELP_API_KEY` is set in `.env` (local) and in Vercel env vars (deployed).

## Local development

```bash
python yelp-server.py
```

Open [http://localhost:8787/reviwo-widget.html](http://localhost:8787/reviwo-widget.html)

Do not open the HTML file directly from disk — the dev server is required for the reviews API.

```env
YELP_API_KEY=your_yelp_api_key_here
MAX_REVIEWS=3
```

## Deploy your own

1. Fork or clone this repo
2. Connect it to [Vercel](https://vercel.com)
3. Add `YELP_API_KEY` (and optionally `MAX_REVIEWS=3`) in the project environment
4. Replace `https://reviwo-pi.vercel.app` in the embed snippet with your deployment URL

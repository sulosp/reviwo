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

### Optional attributes

| Attribute | Description | Default |
|-----------|-------------|---------|
| `data-yelp` | Full Yelp business URL (**required**) | — |
| `data-height` | Initial iframe height in pixels | `480` |
| `data-header-color` | Header background (hex, rgb, hsl) | `#fff` |
| `data-card-color` | Review card background | `#fff` |
| `data-static` | Use cached JSON only (no live API) | off |

### Example with custom colors

```html
<script src="https://reviwo-pi.vercel.app/embed.js" async></script>
<div class="mdg-yelp-widget"
     data-yelp="https://www.yelp.com/biz/mobile-dog-grooming-irvine-2"
     data-height="520"
     data-header-color="#ffffff"
     data-card-color="#f5f5f5"></div>
```

## Local development

```bash
python yelp-server.py
```

Open [http://localhost:8787/reviwo-widget.html](http://localhost:8787/reviwo-widget.html)

Do not open the HTML file directly from disk — the dev server is required for the reviews API.

## Deploy your own

1. Fork or clone this repo
2. Connect it to [Vercel](https://vercel.com)
3. Replace `https://reviwo-pi.vercel.app` in the embed snippet with your deployment URL

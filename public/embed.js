(function () {
    'use strict';

    var script = document.currentScript;
    if (!script || !script.src) return;

    function widgetBaseUrl() {
        if (window.MDG_WIDGET_BASE) {
            return String(window.MDG_WIDGET_BASE).replace(/\/$/, '');
        }
        var url = new URL(script.src);
        return (url.origin + url.pathname).replace(/\/embed\.js(\?.*)?$/, '');
    }

    var base = widgetBaseUrl();
    var containers = document.querySelectorAll('.mdg-yelp-widget');

    containers.forEach(function (container) {
        if (container.getAttribute('data-mdg-embedded') === 'true') return;

        var yelpUrl = container.getAttribute('data-yelp');
        if (!yelpUrl) {
            console.warn('[mdg-yelp-widget] Missing required data-yelp attribute.');
            return;
        }

        container.setAttribute('data-mdg-embedded', 'true');

        var height = container.getAttribute('data-height') || '480';
        var headerColor = container.getAttribute('data-header-color');
        var cardColor = container.getAttribute('data-card-color');
        var isStaticHost = /\.github\.io$/i.test(new URL(base).hostname);

        var embedParams = new URLSearchParams({ yelp: yelpUrl });
        if (headerColor) {
            embedParams.set('headerColor', headerColor);
        }
        if (cardColor) {
            embedParams.set('cardColor', cardColor);
        }
        if (isStaticHost || container.hasAttribute('data-static')) {
            embedParams.set('static', '1');
        } else {
            embedParams.set('api', base + '/api/yelp-reviews');
        }

        var iframe = document.createElement('iframe');
        iframe.src = base + '/embed.html?' + embedParams.toString();
        iframe.title = 'Yelp Reviews';
        iframe.loading = 'lazy';
        iframe.setAttribute('frameborder', '0');
        iframe.setAttribute('scrolling', 'no');
        iframe.style.cssText = 'width:100%;border:none;display:block;min-height:' + height + 'px;';

        window.addEventListener('message', function (event) {
            if (event.origin !== new URL(base).origin) return;
            if (!event.data || event.data.type !== 'mdg-yelp-widget-resize') return;
            if (event.source !== iframe.contentWindow) return;
            iframe.style.height = event.data.height + 'px';
        });

        container.appendChild(iframe);
    });
})();

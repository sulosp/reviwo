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
    var baseOrigin = new URL(base).origin;
    var containers = document.querySelectorAll('.mdg-yelp-widget');

    function renderContainer(container) {
        var yelpUrl = container.getAttribute('data-yelp');
        if (!yelpUrl) {
            console.warn('[mdg-yelp-widget] Missing required data-yelp attribute.');
            return;
        }

        var height = container.getAttribute('data-height') || '480';
        var headerColor = container.getAttribute('data-header-color');
        var cardColor = container.getAttribute('data-card-color');
        var iframe = container.querySelector('iframe[data-mdg-iframe="true"]');

        var embedParams = new URLSearchParams({ yelp: yelpUrl });
        if (headerColor) {
            embedParams.set('headerColor', headerColor);
        }
        if (cardColor) {
            embedParams.set('cardColor', cardColor);
        }
        embedParams.set('api', base + '/api/yelp-reviews');

        var iframeSrc = base + '/embed.html?' + embedParams.toString();

        if (!iframe) {
            iframe = document.createElement('iframe');
            iframe.title = 'Yelp Reviews';
            iframe.loading = 'lazy';
            iframe.setAttribute('frameborder', '0');
            iframe.setAttribute('scrolling', 'no');
            iframe.setAttribute('data-mdg-iframe', 'true');

            window.addEventListener('message', function (event) {
                if (event.origin !== baseOrigin) return;
                if (!event.data || event.data.type !== 'mdg-yelp-widget-resize') return;
                if (event.source !== iframe.contentWindow) return;
                iframe.style.height = event.data.height + 'px';
            });

            container.appendChild(iframe);
        }

        iframe.src = iframeSrc;
        iframe.style.cssText = 'width:100%;border:none;display:block;min-height:' + height + 'px;';
        container.setAttribute('data-mdg-embedded', 'true');
    }

    containers.forEach(function (container) {
        if (container.getAttribute('data-mdg-observed') !== 'true') {
            container.setAttribute('data-mdg-observed', 'true');

            if (typeof MutationObserver !== 'undefined') {
                var observer = new MutationObserver(function (mutations) {
                    for (var i = 0; i < mutations.length; i += 1) {
                        if (mutations[i].type === 'attributes') {
                            renderContainer(container);
                            break;
                        }
                    }
                });

                observer.observe(container, {
                    attributes: true,
                    attributeFilter: ['data-yelp', 'data-height', 'data-header-color', 'data-card-color']
                });
            }
        }

        renderContainer(container);
    });
})();

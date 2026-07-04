(function (global) {
    'use strict';

    const DEFAULT_YELP_URL = 'https://www.yelp.com/biz/mobile-dog-grooming-irvine-2';
    const yelpIcon = '<svg viewBox="0 0 24 24"><path fill="#d32323" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1.5 14.5h-3v-3h3v3zm0-4h-3V7h3v5.5z"/></svg>';

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function starSvg(filled) {
        return `<svg class="star${filled ? '' : ' empty'}" viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>`;
    }

    function renderStars(rating) {
        return Array.from({ length: 5 }, (_, i) => starSvg(i < Math.round(rating))).join('');
    }

    function slugFromYelpUrl(url) {
        const match = String(url || '').match(/\/biz\/([^/?#]+)/);
        return match ? match[1] : null;
    }

    function readInlineReviews() {
        if (global.MDG_YELP_REVIEWS) {
            return global.MDG_YELP_REVIEWS;
        }
        var node = document.getElementById('mdg-yelp-reviews');
        if (node && node.textContent) {
            try {
                return JSON.parse(node.textContent);
            } catch (e) {
                return null;
            }
        }
        return null;
    }

    function inlineMatchesRequest(inline, config) {
        if (!inline || config.yelpUrl) return false;
        return true;
    }

    function resolveDataUrl(config, baseOrigin) {
        const origin = baseOrigin || window.location.origin;
        const yelpUrl = config.yelpUrl;

        if (yelpUrl) {
            const slug = slugFromYelpUrl(yelpUrl);
            const jsonUrl = slug ? `${origin}/reviews/${slug}.json` : null;

            if (config.staticMode) {
                return { jsonUrl, apiUrl: null };
            }

            const apiBase = config.apiUrl || `${origin}/api/yelp-reviews`;
            const url = new URL(apiBase, origin);
            url.searchParams.set('yelp', yelpUrl);
            return { jsonUrl, apiUrl: url.href };
        }

        return {
            jsonUrl: config.jsonUrl || `${origin}/yelp-reviews.json`,
            apiUrl: config.apiUrl || null
        };
    }

    function widgetTemplate(yelpUrl) {
        return `
            <div class="reviews-widget">
                <header class="widget-header">
                    <div class="header-left">
                        <svg class="yelp-logo" viewBox="0 0 40 40" aria-hidden="true">
                            <rect width="40" height="40" rx="4" fill="#d32323" />
                            <path fill="#fff" d="M20 8l2.2 6.8h7.1l-5.7 4.1 2.2 6.8L20 21.6l-5.8 4.1 2.2-6.8-5.7-4.1h7.1L20 8z" />
                        </svg>
                        <div>
                            <div class="header-rating">
                                <span class="rating-number" data-role="headerRating">—</span>
                                <div class="stars" data-role="headerStars" aria-label="Rating"></div>
                            </div>
                            <p class="review-count" data-role="reviewCount">Loading Yelp reviews…</p>
                        </div>
                    </div>
                    <a class="write-review-btn" href="${escapeHtml(yelpUrl)}" target="_blank" rel="noopener noreferrer">Write a review</a>
                </header>
                <div class="carousel-wrap" data-role="carouselWrap">
                    <button class="carousel-arrow prev" data-role="prevBtn" type="button" aria-label="Previous reviews">
                        <svg viewBox="0 0 24 24"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
                    </button>
                    <div class="carousel-viewport">
                        <div class="carousel-track" data-role="carouselTrack">
                            <p class="widget-status">Loading reviews from Yelp…</p>
                        </div>
                    </div>
                    <button class="carousel-arrow next" data-role="nextBtn" type="button" aria-label="Next reviews">
                        <svg viewBox="0 0 24 24"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
                    </button>
                </div>
                <div class="pagination" data-role="pagination" hidden>
                    <div class="carousel-progress" data-role="progressBar" aria-hidden="true">
                        <div class="carousel-progress-fill" data-role="progressFill"></div>
                    </div>
                    <p class="carousel-position" data-role="positionLabel"></p>
                </div>
            </div>
        `;
    }

    function buildCard(review) {
        const card = document.createElement('article');
        card.className = 'review-card';

        const avatarHtml = review.photoUrl
            ? `<img class="author-avatar" src="${escapeHtml(review.photoUrl)}" alt="">`
            : `<div class="author-avatar placeholder">${escapeHtml(review.initial || '?')}</div>`;

        const images = review.images || [];
        const imagesHtml = images.length
            ? `<div class="review-images">${images.map((url) =>
                `<img class="review-image" src="${escapeHtml(url)}" alt="" loading="lazy">`
            ).join('')}</div>`
            : '';

        card.innerHTML = `
            <div class="review-author">
                <div class="author-avatar-wrap">
                    ${avatarHtml}
                    <div class="source-badge">${yelpIcon}</div>
                </div>
                <div class="author-info">
                    <div class="author-name">${escapeHtml(review.name)}</div>
                    <div class="review-date">${escapeHtml(review.date)}</div>
                </div>
            </div>
            <div class="card-stars">${renderStars(review.rating)}</div>
            <p class="review-text">${escapeHtml(review.text)}</p>
            ${imagesHtml}
            <div class="card-footer">
                <img class="yelp-footer-logo" src="yelp-logo.png" alt="Yelp" width="52" height="18" loading="lazy">
            </div>
        `;
        return card;
    }

    function init(container, config) {
        config = config || {};
        const yelpUrl = config.yelpUrl || DEFAULT_YELP_URL;
        const baseOrigin = config.baseOrigin || window.location.origin;
        const { jsonUrl, apiUrl } = resolveDataUrl(config, baseOrigin);

        container.classList.add('mdg-yelp-widget-root');
        container.innerHTML = widgetTemplate(yelpUrl);

        const track = container.querySelector('[data-role="carouselTrack"]');
        const pagination = container.querySelector('[data-role="pagination"]');
        const headerRating = container.querySelector('[data-role="headerRating"]');
        const headerStars = container.querySelector('[data-role="headerStars"]');
        const reviewCountEl = container.querySelector('[data-role="reviewCount"]');
        const wrap = container.querySelector('[data-role="carouselWrap"]');
        const prevBtn = container.querySelector('[data-role="prevBtn"]');
        const nextBtn = container.querySelector('[data-role="nextBtn"]');
        const progressFill = container.querySelector('[data-role="progressFill"]');
        const positionLabel = container.querySelector('[data-role="positionLabel"]');
        const progressBar = container.querySelector('[data-role="progressBar"]');

        let reviews = [];
        let yelpReviewCount = 0;
        let currentIndex = 0;
        let autoplayTimer;
        let visibleCount = 5;

        function getVisibleCount() {
            const w = container.clientWidth || window.innerWidth;
            if (w <= 480) return 1;
            if (w <= 768) return 2;
            if (w <= 992) return 3;
            if (w <= 1200) return 4;
            return 5;
        }

        function getMaxIndex() {
            return Math.max(0, reviews.length - visibleCount);
        }

        /** Small lists scroll one review; large lists jump a full page. */
        function getStep() {
            const maxIndex = getMaxIndex();
            if (maxIndex <= 0) return 1;
            if (maxIndex <= 7) return 1;
            return visibleCount;
        }

        function formatPositionLabel() {
            const total = reviews.length;
            const maxIndex = getMaxIndex();
            if (maxIndex <= 0) return '';

            const start = currentIndex + 1;
            const end = Math.min(currentIndex + visibleCount, total);

            if (visibleCount === 1 && total <= 12) {
                return `Review ${start} of ${total}`;
            }

            if (getStep() > 1) {
                const page = Math.floor(currentIndex / getStep()) + 1;
                const pageTotal = Math.ceil((maxIndex + 1) / getStep());
                let label = `Page ${page} of ${pageTotal} · Showing ${start}–${end} of ${total}`;
                if (yelpReviewCount > total) {
                    label += ` (${yelpReviewCount} on Yelp)`;
                }
                return label;
            }

            let label = `Showing ${start}–${end} of ${total} reviews`;
            if (yelpReviewCount > total) {
                label += ` (${yelpReviewCount} on Yelp)`;
            }
            return label;
        }

        function updateCarousel() {
            visibleCount = getVisibleCount();
            const maxIndex = getMaxIndex();
            if (currentIndex > maxIndex) currentIndex = maxIndex;

            const card = track.querySelector('.review-card');
            if (!card) return;

            const gap = 20;
            const cardWidth = card.offsetWidth + gap;
            track.style.transform = `translateX(-${currentIndex * cardWidth}px)`;

            const isStatic = maxIndex <= 0;
            wrap.classList.toggle('is-static', isStatic);
            prevBtn.hidden = isStatic;
            nextBtn.hidden = isStatic;
            pagination.hidden = isStatic;

            if (!isStatic) {
                const pct = maxIndex === 0 ? 100 : (currentIndex / maxIndex) * 100;
                progressFill.style.width = `${pct}%`;
                progressBar.setAttribute('aria-valuenow', String(Math.round(pct)));
                progressBar.setAttribute('aria-valuemin', '0');
                progressBar.setAttribute('aria-valuemax', '100');
                progressBar.setAttribute('aria-label', formatPositionLabel());
                positionLabel.textContent = formatPositionLabel();
            }

            notifyHeight();
        }

        function notifyHeight() {
            if (window.parent === window) return;
            window.parent.postMessage({
                type: 'mdg-yelp-widget-resize',
                height: container.offsetHeight
            }, '*');
        }

        function next() {
            const maxIndex = getMaxIndex();
            if (maxIndex <= 0) return;
            if (currentIndex >= maxIndex) {
                currentIndex = 0;
            } else {
                currentIndex = Math.min(currentIndex + getStep(), maxIndex);
            }
            updateCarousel();
        }

        function prev() {
            const maxIndex = getMaxIndex();
            if (maxIndex <= 0) return;
            if (currentIndex <= 0) {
                currentIndex = maxIndex;
            } else {
                currentIndex = Math.max(currentIndex - getStep(), 0);
            }
            updateCarousel();
        }

        function resetAutoplay() {
            clearInterval(autoplayTimer);
            if (reviews.length > visibleCount) {
                autoplayTimer = setInterval(next, 5000);
            }
        }

        function showError(message) {
            track.innerHTML = `<p class="widget-status error">${escapeHtml(message)}</p>`;
            reviewCountEl.textContent = 'Could not load reviews';
            notifyHeight();
        }

        function renderReviews(data) {
            reviews = (data.reviews || []).filter((review) => review.text);
            yelpReviewCount = data.reviewCount ?? reviews.length;
            track.innerHTML = '';

            if (!reviews.length) {
                track.innerHTML = '<p class="widget-status error">No reviews found on Yelp.</p>';
                reviewCountEl.textContent = 'No reviews available';
                notifyHeight();
                return;
            }

            const rating = data.rating ?? reviews[0].rating ?? 5;
            headerRating.textContent = Number(rating).toFixed(1);
            headerStars.innerHTML = renderStars(rating);
            headerStars.setAttribute('aria-label', `${rating} out of 5 stars`);

            const count = data.reviewCount ?? reviews.length;
            reviewCountEl.textContent = `${count} review${count === 1 ? '' : 's'} on Yelp`;

            reviews.forEach((review) => track.appendChild(buildCard(review)));
            currentIndex = 0;
            updateCarousel();
            resetAutoplay();
            requestAnimationFrame(notifyHeight);
        }

        async function fetchReviews(url) {
            const response = await fetch(url);
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || `Failed to load reviews (${response.status})`);
            }
            return data;
        }

        async function loadReviews() {
            try {
                let data = config.reviewsData;

                if (!data) {
                    const inline = readInlineReviews();
                    if (inlineMatchesRequest(inline, config)) {
                        data = inline;
                    }
                }

                if (!data) {
                    if (apiUrl) {
                        try {
                            data = await fetchReviews(apiUrl);
                        } catch (err) {
                            if (jsonUrl) {
                                data = await fetchReviews(jsonUrl);
                            } else {
                                throw err;
                            }
                        }
                    } else if (jsonUrl) {
                        data = await fetchReviews(jsonUrl);
                    } else {
                        throw new Error('No review source configured');
                    }
                }

                renderReviews(data);
            } catch (error) {
                showError('Could not load Yelp reviews.');
            }
        }

        container.querySelector('[data-role="nextBtn"]').addEventListener('click', () => {
            next();
            resetAutoplay();
        });
        container.querySelector('[data-role="prevBtn"]').addEventListener('click', () => {
            prev();
            resetAutoplay();
        });
        wrap.addEventListener('mouseenter', () => clearInterval(autoplayTimer));
        wrap.addEventListener('mouseleave', resetAutoplay);
        window.addEventListener('resize', updateCarousel);

        loadReviews();
    }

    global.MDG_YelpWidget = { init, DEFAULT_YELP_URL };
})(typeof window !== 'undefined' ? window : this);

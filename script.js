// Mobile Navigation Toggle
const hamburger = document.querySelector('.hamburger');
const navMenu = document.querySelector('.nav-menu');

hamburger.addEventListener('click', () => {
    hamburger.classList.toggle('active');
    navMenu.classList.toggle('active');
});

// Close mobile menu when clicking on a link
document.querySelectorAll('.nav-link').forEach(n => n.addEventListener('click', () => {
    hamburger.classList.remove('active');
    navMenu.classList.remove('active');
}));

// Navbar scroll effect
window.addEventListener('scroll', () => {
    const navbar = document.querySelector('.navbar');
    if (window.scrollY > 100) {
        navbar.style.padding = '0.5rem 0';
        navbar.style.background = 'rgba(250, 248, 245, 0.98)';
    } else {
        navbar.style.padding = '1rem 0';
        navbar.style.background = 'rgba(250, 248, 245, 0.95)';
    }
});

// Smooth scrolling for in-page anchors and index.html#visit when already on the home page
document.querySelectorAll('a[href^="#"], a[href="index.html#visit"]').forEach((anchor) => {
    anchor.addEventListener('click', function (e) {
        const rawHref = this.getAttribute('href');
        let selector = null;
        if (rawHref && rawHref.startsWith('#')) {
            selector = rawHref;
        } else if (rawHref === 'index.html#visit') {
            selector = '#visit';
        }
        if (!selector) return;
        const target = document.querySelector(selector);
        if (target) {
            e.preventDefault();
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Fade-in animation on scroll
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
        }
    });
}, observerOptions);

// Observe all fade-in elements
document.querySelectorAll('.fade-in').forEach(el => {
    observer.observe(el);
});

// Parallax effect for hero section
window.addEventListener('scroll', () => {
    const scrolled = window.pageYOffset;
    const hero = document.querySelector('.hero');
    if (hero) {
        hero.style.transform = `translateY(${scrolled * 0.5}px)`;
    }
});

// Gallery lightbox functionality
const lightbox = document.createElement('div');
lightbox.className = 'lightbox';
lightbox.innerHTML = `
    <div class="lightbox-content">
        <span class="lightbox-close">&times;</span>
        <img src="" alt="" class="lightbox-image">
        <video class="lightbox-video" controls playsinline style="display:none;"></video>
        <a href="#" class="lightbox-download btn btn-primary" download style="margin-top: 1rem; display: inline-block;">Download</a>
    </div>
`;
document.body.appendChild(lightbox);

const lightboxContentEl = lightbox.querySelector('.lightbox-content');
if (lightboxContentEl) {
    lightboxContentEl.addEventListener('click', (e) => e.stopPropagation());
}

function openGalleryLightboxFromItem(item) {
    const lightboxImage = lightbox.querySelector('.lightbox-image');
    const lightboxVideo = lightbox.querySelector('.lightbox-video');
    const downloadBtn = lightbox.querySelector('.lightbox-download');
    const img = item.querySelector('img');
    const video = item.querySelector('video');

    if (video) {
        lightboxImage.style.display = 'none';
        lightboxVideo.style.display = 'block';
        lightboxVideo.src = video.currentSrc || video.src;
        lightboxVideo.load();
        downloadBtn.href = lightboxVideo.src;
        const vf = (lightboxVideo.src || '').split('/').pop().split('?')[0] || 'video-download';
        downloadBtn.setAttribute('download', vf);
    } else if (img) {
        lightboxVideo.pause();
        lightboxVideo.style.display = 'none';
        lightboxVideo.src = '';
        lightboxImage.style.display = 'block';
        lightboxImage.src = img.src;
        lightboxImage.alt = img.alt;
        downloadBtn.href = img.src;
        const nf = (img.src || '').split('/').pop().split('?')[0] || 'image-download';
        downloadBtn.setAttribute('download', nf);
    }
    lightbox.classList.add('active');
    document.body.style.overflow = 'hidden';
}

// Add lightbox styles
const lightboxStyles = document.createElement('style');
lightboxStyles.textContent = `
    .lightbox {
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.9);
        z-index: 2000;
        cursor: pointer;
    }
    
    .lightbox.active {
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .lightbox-content {
        position: relative;
        max-width: min(96vw, 1200px);
        max-height: 92vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        cursor: default;
    }
    
    .lightbox-image {
        width: auto;
        max-width: 100%;
        max-height: 85vh;
        height: auto;
        object-fit: contain;
        border-radius: 10px;
    }

    .lightbox-video {
        width: auto;
        max-width: 100%;
        max-height: 85vh;
        border-radius: 10px;
    }
    
    .lightbox-close {
        position: absolute;
        top: -40px;
        right: 0;
        color: white;
        font-size: 2rem;
        cursor: pointer;
        background: none;
        border: none;
    }
    
    @media (max-width: 768px) {
        .lightbox-content {
            max-width: 95%;
            max-height: 95%;
        }
        
        .lightbox-close {
            top: -30px;
            font-size: 1.5rem;
        }
    }
`;
document.head.appendChild(lightboxStyles);

document.body.addEventListener('click', (e) => {
    const item = e.target.closest('.gallery-item');
    if (!item || item.closest('.lightbox')) return;
    openGalleryLightboxFromItem(item);
});

lightbox.addEventListener('click', () => {
    lightbox.classList.remove('active');
    const lightboxVideo = lightbox.querySelector('.lightbox-video');
    lightboxVideo.pause();
    lightboxVideo.src = '';
    document.body.style.overflow = 'auto';
});

lightbox.querySelector('.lightbox-close').addEventListener('click', (e) => {
    e.stopPropagation();
    lightbox.classList.remove('active');
    const lightboxVideo = lightbox.querySelector('.lightbox-video');
    lightboxVideo.pause();
    lightboxVideo.src = '';
    document.body.style.overflow = 'auto';
});

// Form validation and submission
const prayerForm = document.getElementById('prayerForm');
if (prayerForm) {
    prayerForm.addEventListener('submit', (e) => {
        e.preventDefault();
        
        // Get form values
        const name = document.getElementById('name').value.trim();
        const email = document.getElementById('email').value.trim();
        const message = document.getElementById('message').value.trim();
        
        // Basic validation
        let isValid = true;
        let errorMessage = '';
        
        if (name.length < 2) {
            isValid = false;
            errorMessage = 'Please enter your name (at least 2 characters)';
        } else if (!isValidEmail(email)) {
            isValid = false;
            errorMessage = 'Please enter a valid email address';
        } else if (message.length < 10) {
            isValid = false;
            errorMessage = 'Please enter a message or prayer request (at least 10 characters)';
        }
        
        if (isValid) {
            // Show success message
            showNotification('Thank you for your message/prayer request. We will get back to you soon.', 'success');
            prayerForm.reset();
        } else {
            showNotification(errorMessage, 'error');
        }
    });
}

// Email validation helper
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// Notification system
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Add notification styles
    const notificationStyles = document.createElement('style');
    if (!document.querySelector('#notification-styles')) {
        notificationStyles.id = 'notification-styles';
        notificationStyles.textContent = `
            .notification {
                position: fixed;
                top: 100px;
                right: 20px;
                padding: 15px 25px;
                border-radius: 10px;
                color: white;
                font-weight: 500;
                z-index: 3000;
                transform: translateX(400px);
                transition: transform 0.3s ease;
                max-width: 350px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            }
            
            .notification-success {
                background: linear-gradient(135deg, #28a745, #20c997);
            }
            
            .notification-error {
                background: linear-gradient(135deg, #dc3545, #c82333);
            }
            
            .notification-info {
                background: linear-gradient(135deg, #17a2b8, #138496);
            }
            
            .notification.show {
                transform: translateX(0);
            }
            
            @media (max-width: 768px) {
                .notification {
                    right: 10px;
                    left: 10px;
                    max-width: none;
                    transform: translateY(-100px);
                }
                
                .notification.show {
                    transform: translateY(0);
                }
            }
        `;
        document.head.appendChild(notificationStyles);
    }
    
    document.body.appendChild(notification);
    
    // Show notification
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);
    
    // Hide notification after 5 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 5000);
}

// Add hover effects to cards
const cards = document.querySelectorAll('.heritage-card, .festival-card');
cards.forEach(card => {
    card.addEventListener('mouseenter', () => {
        card.style.transform = 'translateY(-10px) scale(1.02)';
    });
    
    card.addEventListener('mouseleave', () => {
        card.style.transform = 'translateY(0) scale(1)';
    });
});

// Smooth reveal animation for sections
function revealSections() {
    const sections = document.querySelectorAll('section');
    sections.forEach(section => {
        const sectionTop = section.getBoundingClientRect().top;
        const windowHeight = window.innerHeight;
        
        if (sectionTop < windowHeight - 100) {
            section.style.opacity = '1';
            section.style.transform = 'translateY(0)';
        }
    });
}

// Initialize sections with hidden state
document.addEventListener('DOMContentLoaded', () => {
    const sections = document.querySelectorAll('section');
    sections.forEach(section => {
        section.style.opacity = '0';
        section.style.transform = 'translateY(30px)';
        section.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    });
    
    revealSections();
});

window.addEventListener('scroll', revealSections);

// Add loading animation
window.addEventListener('load', () => {
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.5s ease';
    
    setTimeout(() => {
        document.body.style.opacity = '1';
    }, 100);
});

// Keyboard navigation for lightbox
document.addEventListener('keydown', (e) => {
    if (lightbox.classList.contains('active')) {
        if (e.key === 'Escape') {
            lightbox.classList.remove('active');
            document.body.style.overflow = 'auto';
        }
    }
});

// Calendar modal functionality
const openCalendarBtn = document.getElementById('open-calendar');
const calendarModal = document.getElementById('calendar-modal');
const closeCalendarBtn = document.getElementById('close-calendar');
const calendarPrevBtn = document.getElementById('calendar-prev');
const calendarNextBtn = document.getElementById('calendar-next');
const calendarTitle = document.getElementById('calendar-title');
const calendarImage = document.getElementById('calendar-image');

const CALENDAR_FALLBACK = [
    { name: 'Calendar 1', file: 'calendar/1.jpeg' },
    { name: 'Calendar 2', file: 'calendar/2.jpeg' },
    { name: 'Calendar 3', file: 'calendar/3.jpeg' },
    { name: 'Calendar 4', file: 'calendar/4.jpeg' },
    { name: 'Calendar 5', file: 'calendar/5.jpeg' },
    { name: 'Calendar 6', file: 'calendar/6.jpeg' },
    { name: 'Calendar 7', file: 'calendar/7.jpeg' }
];

let calendarMonths = [...CALENDAR_FALLBACK];

let calendarIndex = 0;

async function loadCalendarData() {
    try {
        const r = await fetch('/api/calendar');
        const data = await r.json();
        const imgs = data.images || [];
        if (imgs.length) {
            calendarMonths = imgs.map((fn, i) => ({ name: `Calendar ${i + 1}`, file: `calendar/${fn}` }));
        } else {
            calendarMonths = [...CALENDAR_FALLBACK];
        }
    } catch (e) {
        calendarMonths = [...CALENDAR_FALLBACK];
    }
}

function renderCalendarMonth() {
    if (!calendarTitle || !calendarImage) return;
    if (!calendarMonths.length) return;
    const month = calendarMonths[calendarIndex];
    calendarTitle.textContent = month.name;
    calendarImage.src = `assets/${month.file}`;
    calendarImage.alt = `${month.name} Calendar`;
}

async function openCalendar() {
    if (!calendarModal) return;
    await loadCalendarData();
    calendarIndex = 0;
    renderCalendarMonth();
    calendarModal.classList.add('active');
    calendarModal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
}

function closeCalendar() {
    if (!calendarModal) return;
    calendarModal.classList.remove('active');
    calendarModal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = 'auto';
}

if (openCalendarBtn) {
    openCalendarBtn.addEventListener('click', () => { openCalendar(); });
}

if (closeCalendarBtn) {
    closeCalendarBtn.addEventListener('click', closeCalendar);
}

if (calendarPrevBtn) {
    calendarPrevBtn.addEventListener('click', () => {
        calendarIndex = (calendarIndex - 1 + calendarMonths.length) % calendarMonths.length;
        renderCalendarMonth();
    });
}

if (calendarNextBtn) {
    calendarNextBtn.addEventListener('click', () => {
        calendarIndex = (calendarIndex + 1) % calendarMonths.length;
        renderCalendarMonth();
    });
}

if (calendarModal) {
    calendarModal.addEventListener('click', (e) => {
        if (e.target === calendarModal) {
            closeCalendar();
        }
    });
}

// Performance optimization - debounce scroll events
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Debounced scroll handlers
const debouncedRevealSections = debounce(revealSections, 50);
const debouncedParallax = debounce(() => {
    const scrolled = window.pageYOffset;
    const hero = document.querySelector('.hero');
    if (hero) {
        hero.style.transform = `translateY(${scrolled * 0.5}px)`;
    }
}, 16);

window.addEventListener('scroll', debouncedRevealSections);
window.addEventListener('scroll', debouncedParallax);

// Add touch support for mobile devices
let touchStartY = 0;
let touchEndY = 0;

document.addEventListener('touchstart', (e) => {
    touchStartY = e.changedTouches[0].screenY;
});

document.addEventListener('touchend', (e) => {
    touchEndY = e.changedTouches[0].screenY;
    handleSwipe();
});

function handleSwipe() {
    if (touchEndY < touchStartY - 50) {
        // Swipe up - could be used for next slide in carousel
        console.log('Swiped up');
    }
    if (touchEndY > touchStartY + 50) {
        // Swipe down - could be used for previous slide
        console.log('Swiped down');
    }
}

// Console welcome message
console.log('%c🙏 Welcome to Piravom Valiyapalli Website 🙏', 'font-size: 20px; color: #d4af37; font-weight: bold;');
console.log('%cSt. Mary\'s Orthodox Syrian Cathedral - A Sacred Pilgrimage of Faith, Tradition and History', 'font-size: 14px; color: #722f37;');

// Church Events Data and Population
const churchEvents = [
    { date: 'January 1 – 6', event: 'Danaha Perunal', image: 'danaha.jpeg' },
    { date: 'March 15 – 19', event: 'Convention', image: 'convention.jpeg' },
    { date: 'March 25', event: 'Vachanipp Perunall', image: 'vachanipp.jpeg' },
    { date: 'March 29', event: 'Oshana', image: 'oshana.jpeg' },
    { date: 'April 2', event: 'Pesaha Vyazham', image: 'pesaha.jpg' },
    { date: 'April 3', event: 'Good Friday', image: 'friday.jpeg' },
    { date: 'April 4', event: 'Holy Saturday', image: 'saturday.jpg' },
    { date: 'April 5', event: 'Easter', image: 'easter.jpg' },
    { date: 'April 5', event: 'Paithel Nercha', image: 'nercha.jpeg' },
    { date: 'April 19', event: 'Paithel Vechoot Nercha', image: 'paithel.jpeg' },
    { date: 'May 6 – 7', event: 'Vishudha Geevarghese Sahadayude Perunal', image: 'geevarghese.jpeg' },
    { date: 'June 29', event: 'Sleeha Perunal', image: 'sleeha.jpeg' },
    { date: 'August 14 – 15', event: 'Vishudha Maadhavinte Vaagippu Perunal', image: 'maadhavu.jpeg' },
    { date: 'October 7 – 8', event: 'Kallitta Perunal', image: 'kallitta.jpeg' },
    { date: 'December 25', event: 'Christmas', image: 'christmas.jpeg' }
];

const fallbackNerchas = [
    { english: 'anitha', malayalam: 'അനിത', price: 10, image: '' },
    { english: 'v. kurbana', malayalam: 'വി. കുർബാന', price: 10, image: '' },
    { english: 'prarthana', malayalam: 'പ്രാർത്ഥന', price: 10, image: '' },
    { english: 'panthrandu paithangulude nercha', malayalam: 'പന്ത്രണ്ടു പൈതങ്ങളുടെ നേർച്ച', price: 500, image: '' }
];

function getCouponImageByIndex(index) {
    const coupons = [
        'assets/coupon/coupon1.jpeg',
        'assets/coupon/coupon2.jpeg',
        'assets/coupon/coupon3.jpeg',
        'assets/coupon/coupon4.jpeg'
    ];
    return coupons[Number(index) % coupons.length];
}

function getNerchaImageSrc(item, index) {
    const fn = item && item.image ? String(item.image).trim() : '';
    if (fn) return `assets/gallery/${fn}`;
    return getCouponImageByIndex(index);
}

let nerchaPurchaseContext = null;

function ensureNerchaPurchaseModal() {
    if (document.getElementById('nercha-purchase-modal')) return;
    const wrap = document.createElement('div');
    wrap.id = 'nercha-purchase-modal';
    wrap.className = 'nercha-purchase-modal';
    wrap.setAttribute('aria-hidden', 'true');
    wrap.innerHTML = `
        <div class="nercha-purchase-modal-backdrop" data-nercha-modal-close></div>
        <div class="nercha-purchase-modal-dialog" role="dialog" aria-modal="true" aria-labelledby="nercha-purchase-title">
            <button type="button" class="nercha-purchase-modal-close" data-nercha-modal-close aria-label="Close">&times;</button>
            <h3 id="nercha-purchase-title" class="nercha-purchase-modal-title">Buy Nercha</h3>
            <p class="nercha-purchase-modal-sub">Please provide your details. This is a request only (no payment).</p>
            <form id="nercha-purchase-form" class="nercha-purchase-form">
                <div class="form-group">
                    <label for="nercha-purchase-name">Name</label>
                    <input type="text" id="nercha-purchase-name" name="name" required autocomplete="name" placeholder="Full name">
                </div>
                <div class="form-group">
                    <label for="nercha-purchase-address">Address</label>
                    <textarea id="nercha-purchase-address" name="address" rows="3" required placeholder="Address"></textarea>
                </div>
                <div class="form-group">
                    <label for="nercha-purchase-phone">Phone Number</label>
                    <input type="tel" id="nercha-purchase-phone" name="phone" required autocomplete="tel" placeholder="Phone number">
                </div>
                <p class="nercha-purchase-modal-sub" style="font-size:0.86rem; margin-bottom: 0.9rem;">
                    By proceeding, you agree to the
                    <a href="/terms.html" target="_blank" rel="noopener noreferrer">Terms &amp; Conditions</a>,
                    <a href="/privacy.html" target="_blank" rel="noopener noreferrer">Privacy Policy</a>, and
                    <a href="/refund.html" target="_blank" rel="noopener noreferrer">Refund Policy</a>.
                </p>
                <div class="nercha-purchase-modal-actions">
                    <button type="button" class="btn btn-secondary-dark" data-nercha-modal-close>Cancel</button>
                    <button type="submit" class="btn btn-primary">Submit</button>
                </div>
            </form>
        </div>
    `;
    document.body.appendChild(wrap);

    wrap.querySelectorAll('[data-nercha-modal-close]').forEach(el => {
        el.addEventListener('click', () => closeNerchaPurchaseModal());
    });
    wrap.addEventListener('click', (e) => {
        if (e.target === wrap) closeNerchaPurchaseModal();
    });
    const purchaseForm = document.getElementById('nercha-purchase-form');
    purchaseForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!nerchaPurchaseContext) return;
        const name = document.getElementById('nercha-purchase-name').value.trim();
        const address = document.getElementById('nercha-purchase-address').value.trim();
        const phone = document.getElementById('nercha-purchase-phone').value.trim();
        try {
            await fetch('/api/purchase', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...nerchaPurchaseContext,
                    name,
                    address,
                    phone
                })
            });
            showNotification('Purchase request recorded.', 'success');
            closeNerchaPurchaseModal();
        } catch (err) {
            showNotification('Purchase request failed.', 'error');
        }
    });
}

function openNerchaPurchaseModal(offering) {
    ensureNerchaPurchaseModal();
    nerchaPurchaseContext = offering;
    const wrap = document.getElementById('nercha-purchase-modal');
    const form = document.getElementById('nercha-purchase-form');
    form.reset();
    wrap.classList.add('active');
    wrap.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    document.getElementById('nercha-purchase-name').focus();
}

function closeNerchaPurchaseModal() {
    const wrap = document.getElementById('nercha-purchase-modal');
    if (!wrap) return;
    wrap.classList.remove('active');
    wrap.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    nerchaPurchaseContext = null;
}

// Function to get month number from month name
function getMonthNumber(monthName) {
    const months = {
        'January': 0, 'February': 1, 'March': 2, 'April': 3,
        'May': 4, 'June': 5, 'July': 6, 'August': 7,
        'September': 8, 'October': 9, 'November': 10, 'December': 11
    };
    return months[monthName];
}

// Function to find upcoming event
function getUpcomingEvent() {
    const today = new Date();
    const currentYear = today.getFullYear();
    let upcomingEvent = null;
    let minDiff = Infinity;

    churchEvents.forEach(eventData => {
        const dateParts = eventData.date.split(' – ');
        const startMonth = dateParts[0].split(' ')[0];
        const startDay = parseInt(dateParts[0].split(' ')[1]);
        
        const eventDate = new Date(currentYear, getMonthNumber(startMonth), startDay);
        
        // If event date has passed this year, check next year
        if (eventDate < today) {
            eventDate.setFullYear(currentYear + 1);
        }
        
        const diff = eventDate - today;
        if (diff > 0 && diff < minDiff) {
            minDiff = diff;
            upcomingEvent = eventData;
        }
    });

    return upcomingEvent;
}

// Function to populate events
function populateEvents() {
    const eventsGrid = document.getElementById('events-grid');
    if (!eventsGrid) {
        return;
    }

    const upcomingEvent = getUpcomingEvent();
    
    // Sort events to put upcoming first
    const sortedEvents = [...churchEvents];
    if (upcomingEvent) {
        const upcomingIndex = sortedEvents.findIndex(e => 
            e.event === upcomingEvent.event && e.date === upcomingEvent.date
        );
        if (upcomingIndex > 0) {
            const [upcoming] = sortedEvents.splice(upcomingIndex, 1);
            sortedEvents.unshift(upcoming);
        }
    }

    eventsGrid.innerHTML = sortedEvents.map((eventData, index) => {
        const isUpcoming = upcomingEvent && 
            eventData.event === upcomingEvent.event && 
            eventData.date === upcomingEvent.date;
        
        return `
            <div class="festival-card ${isUpcoming ? 'upcoming-event' : ''}">
                ${isUpcoming ? '<div class="upcoming-badge">Upcoming Event</div>' : ''}
                <div class="festival-image">
                    <img src="assets/${eventData.image}" alt="${eventData.event}" 
                         onerror="console.error('Image not found: assets/${eventData.image}'); this.style.display='none';">
                    <div class="festival-image-title">${eventData.event}</div>
                </div>
                <div class="festival-icon">
                    <i class="fas fa-calendar-alt"></i>
                </div>
                <h3>${eventData.event}</h3>
                <p class="festival-date">${eventData.date}</p>
                <p>Join us for this sacred celebration at Piravom Valiyapalli.</p>
            </div>
        `;
    }).join('');
    
    console.log('Events populated successfully');
}

// Initialize events when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    populateEvents();
});

let _nerchasOfferingsCache = null;

async function getNerchas() {
    try {
        const res = await fetch('/api/nerchas');
        if (!res.ok) throw new Error('Failed');
        const data = await res.json();
        if (Array.isArray(data.offerings) && data.offerings.length > 0) {
            _nerchasOfferingsCache = data.offerings;
            return data.offerings;
        }
        if (_nerchasOfferingsCache && _nerchasOfferingsCache.length) return _nerchasOfferingsCache;
        return fallbackNerchas;
    } catch (e) {
        if (_nerchasOfferingsCache && _nerchasOfferingsCache.length) return _nerchasOfferingsCache;
        return fallbackNerchas;
    }
}

function renderHomeNerchas(offerings) {
    const container = document.getElementById('nerchas-home-grid');
    if (!container) return;
    container.innerHTML = offerings.map((item, idx) => `
        <div class="nercha-compact-card">
            <div class="nercha-coupon-wrap">
                <img src="${getNerchaImageSrc(item, idx)}" alt="${item.english || 'Nercha'}" class="nercha-coupon-image">
            </div>
            <div class="nercha-ml">${item.malayalam || ''}</div>
            <div class="nercha-en">${item.english || ''}</div>
            <div class="nercha-price">Price: ${item.price ?? 0}</div>
            <button type="button" class="btn btn-primary nercha-buy-btn" data-index="${idx}" style="margin-top: 0.7rem;">Buy</button>
        </div>
    `).join('');

    container.querySelectorAll('.nercha-buy-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const item = offerings[Number(btn.dataset.index)];
            openNerchaPurchaseModal(item);
        });
    });
}

const LIVE_STREAM_OFF_AIR_INNER = `
    <div class="video-content">
        <p>Live is not right now</p>
    </div>
`;

function inferLiveKindFromUrl(url) {
    const u = (url || '').trim().toLowerCase();
    if (!u) return '';
    if (u.includes('youtu.be') || u.includes('youtube.com')) return 'youtube';
    if (u.includes('facebook.com') || u.includes('fb.com') || u.includes('fb.watch')) return 'facebook';
    return '';
}

function normalizeLiveStreamUrl(url) {
    let u = (url || '').trim();
    if (!u) return '';
    if (!/^https?:\/\//i.test(u)) u = 'https://' + u;
    u = u.replace(/^(https?:\/\/)m\.facebook\.com/i, '$1www.facebook.com');
    u = u.replace(/^(https?:\/\/)m\.youtube\.com/i, '$1www.youtube.com');
    return u;
}

function getFacebookJoinUrlFromStored(rawUrl) {
    try {
        const u = new URL((rawUrl || '').trim());
        if (!/\/plugins\/video\.php/i.test(u.pathname)) return '';
        const inner = u.searchParams.get('href');
        if (inner) return normalizeLiveStreamUrl(decodeURIComponent(inner));
    } catch (e) {}
    return '';
}

function isFacebookPluginVideoUrl(url) {
    return /facebook\.com\/plugins\/video\.php/i.test(url || '');
}

function buildYoutubeEmbedSrc(watchUrl) {
    const normalized = normalizeLiveStreamUrl(watchUrl);
    if (!normalized) return '';
    try {
        const u = new URL(normalized);
        const host = u.hostname.replace(/^www\./i, '').toLowerCase();
        if (host === 'youtu.be') {
            const id = u.pathname.replace(/^\//, '').split('/')[0];
            return id ? `https://www.youtube.com/embed/${id}` : '';
        }
        if (host === 'youtube.com' || host === 'm.youtube.com' || host === 'youtube-nocookie.com') {
            if (u.pathname.startsWith('/embed/')) {
                return `${u.origin}${u.pathname}${u.search}`;
            }
            const v = u.searchParams.get('v');
            if (v) return `https://www.youtube.com/embed/${v}`;
            const liveM = u.pathname.match(/^\/live\/([^/?]+)/);
            if (liveM) return `https://www.youtube.com/embed/${liveM[1]}`;
            const shortM = u.pathname.match(/^\/shorts\/([^/?]+)/);
            if (shortM) return `https://www.youtube.com/embed/${shortM[1]}`;
        }
    } catch (e) {}
    return '';
}

function buildFacebookEmbedSrc(rawOrNormalized) {
    const normalized = normalizeLiveStreamUrl(rawOrNormalized);
    if (!normalized) return '';
    if (isFacebookPluginVideoUrl(normalized)) return normalized;
    return `https://www.facebook.com/plugins/video.php?href=${encodeURIComponent(normalized)}&show_text=false&width=560&height=315`;
}

async function getLiveStreamConfig() {
    try {
        const res = await fetch('/api/live-link');
        if (!res.ok) throw new Error('No live link');
        const data = await res.json();
        const url = (data.url || '').trim();
        let kind = (data.kind || '').trim().toLowerCase();
        if (kind !== 'facebook' && kind !== 'youtube') kind = '';
        if (url && !kind) kind = inferLiveKindFromUrl(url);
        return { url, kind };
    } catch (e) {
        return { url: '', kind: '' };
    }
}

function applyLiveStream(config) {
    const rawUrl = config && config.url ? String(config.url).trim() : '';
    let kind = config && config.kind ? String(config.kind).trim().toLowerCase() : '';
    const normalized = normalizeLiveStreamUrl(rawUrl);
    if (rawUrl && (!kind || (kind !== 'facebook' && kind !== 'youtube'))) {
        kind = inferLiveKindFromUrl(normalized) || kind;
    }
    if (rawUrl && !kind) kind = inferLiveKindFromUrl(normalized);

    let joinUrl = normalized;
    if (kind === 'facebook') {
        joinUrl = getFacebookJoinUrlFromStored(rawUrl) || normalized;
    }

    const joinButtons = document.querySelectorAll('.join-live-btn');
    const placeholder = document.querySelector('.video-placeholder');
    joinButtons.forEach((btn) => {
        btn.href = joinUrl || '#';
        if (joinUrl) {
            btn.setAttribute('target', '_blank');
            btn.setAttribute('rel', 'noopener noreferrer');
        } else {
            btn.removeAttribute('target');
            btn.removeAttribute('rel');
        }
    });

    if (!placeholder) return;

    if (!rawUrl || !normalized || !kind) {
        placeholder.innerHTML = LIVE_STREAM_OFF_AIR_INNER;
        return;
    }

    let embedSrc = '';
    if (kind === 'youtube') {
        embedSrc = buildYoutubeEmbedSrc(normalized);
    } else if (kind === 'facebook') {
        embedSrc = buildFacebookEmbedSrc(rawUrl || normalized);
    }

    if (!embedSrc) {
        placeholder.innerHTML = LIVE_STREAM_OFF_AIR_INNER;
        return;
    }

    const title = kind === 'youtube' ? 'YouTube Live' : 'Facebook Live';
    const safeSrc = embedSrc.replace(/"/g, '&quot;');
    placeholder.innerHTML = `<iframe title="${title}" src="${safeSrc}" width="100%" height="100%" style="border:none;overflow:hidden;min-height:280px;" scrolling="no" frameborder="0" allow="autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share" allowfullscreen></iframe>`;

    const iframe = placeholder.querySelector('iframe');
    if (iframe) {
        iframe.addEventListener('error', () => {
            placeholder.innerHTML = LIVE_STREAM_OFF_AIR_INNER;
        });
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    if (document.getElementById('nerchas-home-grid')) {
        const offerings = await getNerchas();
        renderHomeNerchas(offerings);
    }
    const liveCfg = await getLiveStreamConfig();
    applyLiveStream(liveCfg);
});

document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    const m = document.getElementById('nercha-purchase-modal');
    if (m && m.classList.contains('active')) {
        closeNerchaPurchaseModal();
    }
});

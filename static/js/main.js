document.addEventListener('DOMContentLoaded', () => {
    // === TEMA DEĞİŞTİRME ===
    const themeToggleBtn = document.getElementById('theme-toggle');
    function setTheme(theme) {
        if (theme === 'light') {
            document.body.classList.add('light-theme');
            document.body.classList.remove('dark-theme');
            localStorage.setItem('socento-theme', 'light');
        } else {
            document.body.classList.remove('light-theme');
            document.body.classList.add('dark-theme');
            localStorage.setItem('socento-theme', 'dark');
        }
    }
    const savedTheme = localStorage.getItem('socento-theme');
    if (savedTheme === 'light') setTheme('light');
    else setTheme('dark');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', function () {
            if (document.body.classList.contains('light-theme')) {
                setTheme('dark');
            } else {
                setTheme('light');
            }
        });
    }

    // === PRELOADER ===
    const preloader = document.getElementById('preloader');
    const mainContent = document.getElementById('main-content');
    if (preloader && mainContent) {
        setTimeout(() => {
            preloader.classList.add('hidden');
            mainContent.style.opacity = '1';
            mainContent.style.transform = 'translateY(0)';
            preloader.addEventListener('transitionend', () => preloader.style.display = 'none');
        }, 300);
    }

    // === MOBİL MENÜ YÖNETİMİ (YENİ EKLENEN) ===
    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
    const mobileNavLinks = document.getElementById('nav-links-mobile');

    if (mobileMenuToggle && mobileNavLinks) {
        mobileMenuToggle.addEventListener('click', function() {
            if (mobileNavLinks.style.display === 'flex') {
                mobileNavLinks.style.display = 'none';
            } else {
                mobileNavLinks.style.display = 'flex';
            }
        });
    }

    // === EVRENSEL AKSİYON YÖNETİCİSİ (YENİ) ===
    const handleActionClick = async (e) => {
        const button = e.target.closest('.action-button');
        if (!button) return;

        e.preventDefault();
        const action = button.dataset.action;
        let url = '';
        const options = { method: 'POST', headers: { 'Content-Type': 'application/json' } };

        // YENİ: Blog Tepki Aksiyonları
        if (action === 'blog-like' || action === 'blog-dislike') {
            const blogCard = button.closest('[data-blog-id]');
            if (!blogCard) return;
            const blogId = blogCard.dataset.blogId;
            url = `/blog/${blogId}/react`;
            options.body = JSON.stringify({ reaction: action === 'blog-like' ? 'like' : 'dislike' });
        } else {
            const postId = button.closest('[data-post-id]')?.dataset.postId;
            if (!postId) {
                let username = button.closest('[data-username]')?.dataset.username || document.querySelector('.profile-main-content-area[data-username]')?.dataset.username;
                if (!username) return;
                url = action === 'follow' ? `/follow/${username}` : `/unfollow/${username}`;
            } else if (action === 'rise' || action === 'fade') {
                url = `/echo/${postId}/${action}`;
            } else if (action === 'like') {
                if (postId.startsWith('echo-')) {
                    const id = postId.replace('echo-', '');
                    url = `/premium_echo/${id}/like`;
                } else if (postId.startsWith('clip-')) {
                    const id = postId.replace('clip-', '');
                    url = `/premium_clip/${id}/like`;
                } else {
                    url = `/like_post/${postId}`;
                }
            } else if (action === 'lift') {
                if (postId.startsWith('echo-')) {
                    const id = postId.replace('echo-', '');
                    url = `/premium_echo/${id}/lift`;
                } else if (postId.startsWith('clip-')) {
                    const id = postId.replace('clip-', '');
                    url = `/premium_clip/${id}/lift`;
                } else {
                    url = `/post/${postId}/lift`;
                }
            } else {
                return;
            }
        }

        try {
            const response = await fetch(url, options);
            if (!response.ok) throw new Error('Network response was not ok');
            const data = await response.json();
            if (data.success) {
                updateUI(button, action, data);
            } else {
                if (data.error) alert(data.error);
            }
        } catch (err) {
            console.error('Action failed:', err);
            alert('Bir hata oluştu. Lütfen tekrar deneyin.');
        }
    };
    document.body.addEventListener('click', handleActionClick);

    // === UI GÜNCELLEME FONKSİYONU (YENİLEŞTİRİLMİŞ) ===
    const updateCountWithAnimation = (element, newText) => {
        if (!element) return;
        element.style.transition = 'opacity 0.15s ease-out';
        element.style.opacity = '0';
        setTimeout(() => {
            element.textContent = newText;
            element.style.opacity = '1';
        }, 150);
    };

    const updateUI = (button, action, data) => {
        // YENİ: Blog tepki UI güncellemesi
        if (action === 'blog-like' || action === 'blog-dislike') {
            const blogCard = button.closest('[data-blog-id]');
            if (!blogCard) return;

            const likeBtn = blogCard.querySelector('[data-action="blog-like"]');
            const dislikeBtn = blogCard.querySelector('[data-action="blog-dislike"]');
            const likeCountEl = likeBtn.querySelector('.like-count');
            const dislikeCountEl = dislikeBtn.querySelector('.dislike-count');

            likeCountEl.textContent = data.like_count;
            dislikeCountEl.textContent = data.dislike_count;

            const wasActive = button.style.backgroundColor !== 'rgb(51, 65, 85)';

            likeBtn.style.backgroundColor = '#334155';
            dislikeBtn.style.backgroundColor = '#334155';

            if (!wasActive) {
                button.style.backgroundColor = (action === 'blog-like') ? '#27ae60' : '#c0392b';
            }
            return;
        }

        // Takip Et/Takibi Bırak aksiyonları
        if (action === 'follow' || action === 'unfollow') {
            if (data.success) {
                // Buton metnini ve data-action özniteliğini güncelle
                if (action === 'follow') {
                    button.textContent = 'Takibi Bırak';
                    button.dataset.action = 'unfollow';
                    button.classList.remove('profile-follow-btn');
                    button.classList.add('profile-unfollow-btn');
                } else { // action === 'unfollow'
                    button.textContent = 'Takip Et';
                    button.dataset.action = 'follow';
                    button.classList.remove('profile-unfollow-btn');
                    button.classList.add('profile-follow-btn');
                }

                // Takipçi sayısını güncelle (eğer varsa)
                const followerCountElement = document.querySelector('.stat-number.follower-count');
                if (followerCountElement && data.count !== undefined) {
                    updateCountWithAnimation(followerCountElement, data.count);
                }
            }
            return; // Takip aksiyonları için buradan çık
        }


        const card = button.closest('[data-post-id]');
        if (!card) return;

        if (action === 'like') {
            if ('liked' in data) {
                button.classList.toggle('liked', data.liked);
                const icon = button.querySelector('i');
                if (icon) icon.className = data.liked ? 'fas fa-heart' : 'far fa-heart';
            }
            let count = data.count ?? data.like_count;
            let likeCount = card.querySelector('.like-count') || button.querySelector('span');
            if (likeCount && count !== undefined) {
                updateCountWithAnimation(likeCount, count + (likeCount.classList.contains('like-count') ? ' Beğeni' : ''));
            }
        }

        if (action === 'lift') {
            if ('lifted' in data) {
                button.classList.toggle('lifted', data.lifted);
            }
            let count = data.lift_count ?? data.count;
            let liftCount = card.querySelector('.lift-count') || button.querySelector('span');
            if (liftCount && count !== undefined) {
                updateCountWithAnimation(liftCount, count + (liftCount.classList.contains('lift-count') ? ' Lift' : ''));
            }
        }

        if (action === 'rise') {
            button.classList.toggle('risen', data.risen);
            const icon = button.querySelector('i');
            if (icon) icon.className = data.risen ? 'fas fa-arrow-alt-circle-up' : 'far fa-arrow-alt-circle-up';
            let riseCount = card.querySelector('.rise-count');
            if (riseCount) updateCountWithAnimation(riseCount, data.rise_count);

            const fadeBtn = card.querySelector('.fade-button');
            if (fadeBtn) fadeBtn.classList.toggle('faded', data.faded);
            const fadeIcon = fadeBtn?.querySelector('i');
            if (fadeIcon) fadeIcon.className = data.faded ? 'fas fa-arrow-alt-circle-down' : 'far fa-arrow-alt-circle-down';
            let fadeCount = card.querySelector('.fade-count');
            if (fadeCount) updateCountWithAnimation(fadeCount, data.fade_count);
        }

        if (action === 'fade') {
            button.classList.toggle('faded', data.faded);
            const icon = button.querySelector('i');
            if (icon) icon.className = data.faded ? 'fas fa-arrow-alt-circle-down' : 'far fa-arrow-alt-circle-down';
            let fadeCount = card.querySelector('.fade-count');
            if (fadeCount) updateCountWithAnimation(fadeCount, data.fade_count);

            const riseBtn = card.querySelector('.rise-button');
            if (riseBtn) riseBtn.classList.toggle('risen', data.risen);
            const riseIcon = riseBtn?.querySelector('i');
            if (riseIcon) riseIcon.className = data.risen ? 'fas fa-arrow-alt-circle-up' : 'far fa-arrow-alt-circle-up';
            let riseCount = card.querySelector('.rise-count');
            if (riseCount) updateCountWithAnimation(riseCount, data.rise_count);
        }
    };

    // === AKIŞ YÖNETİMİ ===
    const mainWrapper = document.querySelector('.main-content-flex-wrapper');
    if (mainWrapper) {
        const feedContainer = document.getElementById('feed-container');
        const initialFeed = new URLSearchParams(window.location.search).get('feed') || mainWrapper.dataset.initialFeed || 'posts';
        const allNavLinks = document.querySelectorAll('.main-nav-link, .mobile-bottom-nav .nav-item[data-feed], .feed-selector-btn');
        const activeLine = document.querySelector('.feed-view-selector .active-line');
        const sidebarContents = document.querySelectorAll('.left-sidebar .sidebar-content');

        const setActiveNav = (feedType) => {
            allNavLinks.forEach(link => {
                link.classList.toggle('active', link.dataset.feed === feedType);
            });
            if (activeLine) {
                const activeBtn = document.querySelector(`.feed-selector-btn[data-feed="${feedType}"]`);
                if (activeBtn) {
                    activeLine.style.width = `${activeBtn.offsetWidth}px`;
                    activeLine.style.left = `${activeBtn.offsetLeft}px`;
                }
            }
            if (sidebarContents) {
                sidebarContents.forEach(content => {
                    content.style.display = content.dataset.feedContext === feedType ? 'block' : 'none';
                });
            }
        };

        const loadFeed = async (feedType, pushToHistory = true) => {
            if (!feedContainer) return;
            document.body.classList.toggle('clips-active', feedType === 'clips');
            feedContainer.innerHTML = '<div class="feed-loader"><i class="fas fa-spinner fa-spin"></i></div>';
            document.onkeydown = null;

            try {
                const response = await fetch(`/load_feed/${feedType}`);
                if (!response.ok) throw new Error(`Network response was not ok: ${response.statusText}`);
                const newContent = await response.text();

                feedContainer.style.opacity = '0';
                setTimeout(() => {
                    feedContainer.innerHTML = newContent;
                    feedContainer.style.opacity = '1';
                    if (pushToHistory) {
                        const url = feedType === 'posts' ? window.location.pathname.split('?')[0] : `/?feed=${feedType}`;
                        history.pushState({ feed: feedType }, '', url);
                    }
                    setActiveNav(feedType);
                    if (feedType === 'clips') {
                        initializeClipsViewer();
                    }
                }, 150);
            } catch (error) {
                console.error('Feed could not be loaded:', error);
                feedContainer.innerHTML = `<p class="error-message">İçerik yüklenemedi. Lütfen daha sonra tekrar deneyin.</p>`;
            }
        };

        function initializeClipsViewer() {
            const clipsContainer = document.getElementById('clips-container');
            if (!clipsContainer) return;
            const slides = clipsContainer.querySelectorAll('.clip-slide');
            if (slides.length === 0) return;

            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    const video = entry.target.querySelector('.clip-video');
                    if (!video) return;
                    if (entry.isIntersecting) {
                        if (!video.src) video.src = entry.target.dataset.videoUrl;
                        video.play().catch(() => { video.muted = true; video.play(); });
                    } else {
                        video.pause();
                    }
                });
            }, { threshold: 0.7 });

            slides.forEach(slide => observer.observe(slide));

            document.onkeydown = (e) => {
                if (document.body.classList.contains('clips-active')) {
                    if (e.key === 'ArrowDown') clipsContainer.scrollBy({ top: clipsContainer.clientHeight, behavior: 'smooth' });
                    else if (e.key === 'ArrowUp') clipsContainer.scrollBy({ top: -clipsContainer.clientHeight, behavior: 'smooth' });
                }
            };
        }

        allNavLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const feedType = link.dataset.feed;
                if (feedType) loadFeed(feedType);
            });
        });

        window.addEventListener('popstate', (e) => {
            const feed = (e.state && e.state.feed) ? e.state.feed : 'posts';
            loadFeed(feed, false);
        });

        loadFeed(initialFeed, false);
    }

    // === BLINK SİSTEMİ (YENİ VE GÜNCELLENMİŞ) ===
    const blinksData = window.blinksData; // home.html'den gelen global veri
    const customBlinkViewer = document.getElementById('customBlinkViewer');
    const blinkUserAvatar = customBlinkViewer.querySelector('.blink-user-avatar');
    const blinkUserUsername = customBlinkViewer.querySelector('.blink-user-username');
    const blinkProgressBars = customBlinkViewer.querySelector('.blink-progress-bars');
    const blinkMediaImage = customBlinkViewer.querySelector('.blink-media-image');
    const blinkMediaVideo = customBlinkViewer.querySelector('.blink-media-video');
    const blinkTextContent = customBlinkViewer.querySelector('.blink-text-content');
    const blinkCloseBtn = customBlinkViewer.querySelector('.blink-close-btn');
    const prevBlinkBtn = customBlinkViewer.querySelector('.prev-btn');
    const nextBlinkBtn = customBlinkViewer.querySelector('.next-btn');

    let currentUserBlinks = null; // Şu an gösterilen kullanıcının blinkler dizisi
    let currentBlinkIndex = 0; // Şu anki blink'in indeksi
    let autoAdvanceTimeout = null; // Otomatik ilerleme zamanlayıcısı

    // Blinks görüntüleyiciyi açma
    document.querySelectorAll('.view-blinks-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const userId = this.dataset.userId;
            currentUserBlinks = blinksData[userId];
            currentBlinkIndex = 0;
            
            if (currentUserBlinks && currentUserBlinks.length > 0) {
                document.body.classList.add('blinks-active'); // Blink aktif sınıfını ekle
                customBlinkViewer.classList.add('is-active');
                displayBlink(currentBlinkIndex);
            }
        });
    });

    // Blinks görüntüleyiciyi kapatma
    blinkCloseBtn.addEventListener('click', closeBlinkViewer);
    customBlinkViewer.addEventListener('click', function(e) {
        if (e.target === customBlinkViewer) { // Sadece dış katmana tıklanırsa kapat
            closeBlinkViewer();
        }
    });

    // Esc tuşuyla kapatma
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && customBlinkViewer.classList.contains('is-active')) {
            closeBlinkViewer();
        }
    });

    // İleri/Geri butonları
    nextBlinkBtn.addEventListener('click', () => navigateBlink(1));
    prevBlinkBtn.addEventListener('click', () => navigateBlink(-1));

    // Klavyeyle ileri/geri gitme
    document.addEventListener('keydown', function(e) {
        if (customBlinkViewer.classList.contains('is-active')) {
            if (e.key === 'ArrowRight') {
                navigateBlink(1);
            } else if (e.key === 'ArrowLeft') {
                navigateBlink(-1);
            }
        }
    });

    function displayBlink(index) {
        if (!currentUserBlinks || index < 0 || index >= currentUserBlinks.length) {
            closeBlinkViewer();
            return;
        }

        currentBlinkIndex = index;
        const blink = currentUserBlinks[currentBlinkIndex];

        // Temizle
        blinkMediaImage.style.display = 'none';
        blinkMediaVideo.style.display = 'none';
        blinkTextContent.style.display = 'none';
        blinkMediaVideo.pause();
        blinkMediaVideo.currentTime = 0;

        // Kullanıcı bilgileri
        blinkUserAvatar.src = blink.profile_picture_url;
        blinkUserUsername.textContent = '@' + blink.username;
        blinkUserUsername.href = `/profile/${blink.username}`; // Profil linki

        // İçerik yükle
        if (blink.image_url) {
            blinkMediaImage.src = blink.image_url;
            blinkMediaImage.style.display = 'block';
        } else if (blink.video_url) {
            blinkMediaVideo.src = blink.video_url;
            blinkMediaVideo.style.display = 'block';
            blinkMediaVideo.play().catch(e => console.log("Video auto-play failed:", e));
        } else if (blink.text_content) {
            blinkTextContent.textContent = blink.text_content;
            blinkTextContent.style.display = 'block';
        }

        updateProgressBars();
        startAutoAdvance();
    }

    function updateProgressBars() {
        blinkProgressBars.innerHTML = ''; // Önceki barları temizle
        currentUserBlinks.forEach((_, i) => {
            const barWrapper = document.createElement('div');
            barWrapper.classList.add('progress-bar-wrapper');
            const bar = document.createElement('div');
            bar.classList.add('progress-bar');
            barWrapper.appendChild(bar);
            blinkProgressBars.appendChild(barWrapper);

            if (i < currentBlinkIndex) {
                bar.style.width = '100%'; // Geçilen barlar tam dolu
            } else if (i === currentBlinkIndex) {
                // Aktif barın animasyonu CSS ile yönetilecek
                bar.style.width = '0%'; // Animasyona başlamadan önce 0'a çek
                bar.style.animation = `fillProgressBar 5s linear forwards`; // 5 saniye sürecek
            } else {
                bar.style.width = '0%'; // Henüz gelmemiş barlar boş
            }
        });
    }

    function startAutoAdvance() {
        clearTimeout(autoAdvanceTimeout);
        autoAdvanceTimeout = setTimeout(() => {
            navigateBlink(1);
        }, 5000); // Her blink 5 saniye görünsün
    }

    function navigateBlink(direction) {
        let newIndex = currentBlinkIndex + direction;
        if (newIndex >= 0 && newIndex < currentUserBlinks.length) {
            displayBlink(newIndex);
        } else {
            // Son blink'ten sonra veya ilk blink'ten önce, görüntüleyiciyi kapat
            closeBlinkViewer();
        }
    }

    function closeBlinkViewer() {
        customBlinkViewer.classList.remove('is-active');
        document.body.classList.remove('blinks-active'); // Blink aktif sınıfını kaldır
        blinkMediaVideo.pause();
        blinkMediaVideo.currentTime = 0;
        clearTimeout(autoAdvanceTimeout);
        currentUserBlinks = null; // Verileri sıfırla
        currentBlinkIndex = 0;
    }
});
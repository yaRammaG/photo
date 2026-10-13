(function () {
  "use strict";

  /* ---------- Lenis 平滑滚动 ---------- */
  var lenis = null;
  if (window.Lenis) {
    lenis = new Lenis({ duration: 1.1 });
    if (window.gsap && window.ScrollTrigger) {
      lenis.on("scroll", window.ScrollTrigger.update);
      window.gsap.ticker.add(function (time) {
        lenis.raf(time * 1000);
      });
      window.gsap.ticker.lagSmoothing(0);
    } else {
      var rafLoop = function (time) {
        lenis.raf(time);
        requestAnimationFrame(rafLoop);
      };
      requestAnimationFrame(rafLoop);
    }
  }
  window.__lenis = lenis;

  /* ---------- 导航：滚动后渐暗 ---------- */
  var nav = document.getElementById("nav");
  function onScroll() {
    if (nav) nav.classList.toggle("nav-scrolled", (window.scrollY || 0) > 40);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---------- 锚点平滑滚动 ---------- */
  Array.prototype.forEach.call(
    document.querySelectorAll('a[href^="#"]'),
    function (a) {
      a.addEventListener("click", function (e) {
        var href = a.getAttribute("href");
        e.preventDefault();
        if (href === "#") {
          if (lenis) lenis.scrollTo(0);
          else window.scrollTo({ top: 0, behavior: "smooth" });
          return;
        }
        var target = document.querySelector(href);
        if (!target) return;
        if (lenis) lenis.scrollTo(target);
        else target.scrollIntoView({ behavior: "smooth" });
      });
    }
  );

  /* ---------- 入场动画：仅 opacity / transform / clip-path，≤0.6s ---------- */
  if (window.gsap && window.ScrollTrigger) {
    var gsap = window.gsap;
    gsap.registerPlugin(window.ScrollTrigger);

    var heroTitle = document.querySelector(".hero-title, .cover-title");
    if (heroTitle) {
      gsap.from(heroTitle, {
        opacity: 0,
        y: 24,
        duration: 0.6,
        ease: "power2.out",
        delay: 0.15,
      });
    }

    var photos = gsap.utils.toArray(".photo");
    if (photos.length) {
      gsap.set(photos, { clipPath: "inset(0 0 100% 0)", y: 40 });
      window.ScrollTrigger.batch(photos, {
        start: "top 88%",
        once: true,
        onEnter: function (batch) {
          gsap.to(batch, {
            clipPath: "inset(0 0 0% 0)",
            y: 0,
            duration: 0.6,
            ease: "power2.out",
            stagger: 0.08,
            overwrite: true,
          });
        },
      });
    }
  }

  /* ---------- PhotoSwipe 灯箱 ---------- */
  var figures = Array.prototype.slice.call(document.querySelectorAll(".photo"));
  if (!figures.length || !window.PhotoSwipeLightbox || !window.PhotoSwipe) return;

  var dataSource = figures.map(function (f) {
    var img = f.querySelector("img");
    return {
      src: f.dataset.display,
      w: parseInt(img.getAttribute("width"), 10),
      h: parseInt(img.getAttribute("height"), 10),
      full: f.dataset.full,
      exif: f.dataset.exif || "",
      msrc: img.getAttribute("src"),
      alt: img.alt,
    };
  });

  var lightbox = new PhotoSwipeLightbox({
    dataSource: dataSource,
    pswpModule: window.PhotoSwipe,
    bgOpacity: 0.95,
    counter: true,
    zoom: true,
  });

  var viewFullBtn = null;

  lightbox.on("uiRegister", function () {
    var pswp = lightbox.pswp;

    pswp.ui.registerElement({
      name: "view-full",
      className: "pswp__view-full",
      title: "查看原图",
      isButton: true,
      html: "查看原图",
      appendTo: "bar",
      onClick: function () {
        var slide = pswp.currSlide;
        if (slide.data.full && slide.data.src !== slide.data.full) {
          slide.data.src = slide.data.full;
          pswp.refreshSlideContent(pswp.currIndex);
          if (viewFullBtn) viewFullBtn.textContent = "已显示原图";
        }
      },
    });

    pswp.ui.registerElement({
      name: "exif-caption",
      className: "pswp__exif",
      appendTo: "root",
      onInit: function (el, p) {
        var update = function () {
          el.textContent = p.currSlide ? p.currSlide.data.exif : "";
        };
        update();
        p.on("change", update);
      },
    });
  });

  lightbox.on("change", function (pswp) {
    // 200ms 轻微缩放过渡：scale 独立属性，不干扰 pswp 自管的 transform
    var slide = pswp.currSlide;
    var el = slide && slide.content && slide.content.element;
    if (el && el.animate) {
      try {
        el.animate(
          [{ scale: "0.985" }, { scale: "1" }],
          { duration: 200, easing: "ease-out" }
        );
      } catch (err) {
        /* 浏览器不支持独立 scale 属性时静默跳过 */
      }
    }
    if (viewFullBtn && slide.data.src !== slide.data.full) {
      viewFullBtn.textContent = "查看原图";
    }
  });

  lightbox.on("beforeOpen", function () {
    if (window.__lenis) window.__lenis.stop();
  });

  lightbox.on("closingAnimationEnd", function () {
    if (window.__lenis) window.__lenis.start();
  });

  figures.forEach(function (f, i) {
    f.addEventListener("click", function () {
      lightbox.loadAndOpen(i, dataSource);
    });
  });

  lightbox.init();
})();

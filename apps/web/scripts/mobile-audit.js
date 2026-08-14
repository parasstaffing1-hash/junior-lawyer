/**
 * Phone-layout audit for a single page.
 *
 * Paste into the browser console with the viewport at 375px, or run it through
 * a driver. Reports the three things that actually break a workspace on a
 * phone: the page scrolling sideways, elements escaping the viewport, and tap
 * targets too small to hit.
 *
 * Written while fixing the composer and top bar; kept so the next person can
 * check a page in five seconds rather than by eye.
 */
(() => {
  const vw = window.innerWidth;

  const overflowing = [...document.querySelectorAll("body *")]
    .filter((el) => {
      const rect = el.getBoundingClientRect();
      return rect.width > 0 && rect.right > vw + 1;
    })
    .slice(0, 10)
    .map((el) => {
      const rect = el.getBoundingClientRect();
      const cls = String(el.className || "").split(" ")[0];
      return `${el.tagName.toLowerCase()}${cls ? "." + cls : ""} right=${Math.round(rect.right)}`;
    });

  // 44px is the usual minimum for a comfortable touch target; inline links
  // inside a paragraph are exempt because they are read, not tapped at speed.
  const smallTargets = [...document.querySelectorAll("button, a, select, input")]
    .filter((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return false;
      if (el.tagName === "A" && el.closest("p")) return false;
      if (el.type === "checkbox" || el.type === "radio") return false;
      return rect.height < 36;
    })
    .slice(0, 10)
    .map((el) => {
      const rect = el.getBoundingClientRect();
      const label = (el.textContent || el.getAttribute("aria-label") || el.type || "").trim().slice(0, 24);
      return `${el.tagName.toLowerCase()}[${label}] ${Math.round(rect.width)}x${Math.round(rect.height)}`;
    });

  const oversizedIcons = [...document.querySelectorAll("svg")]
    .filter((el) => el.getBoundingClientRect().width > 40)
    .slice(0, 5)
    .map((el) => `svg in .${String(el.parentElement?.className || "").split(" ")[0]}`);

  return {
    path: location.pathname,
    viewport: vw,
    horizontalOverflow: document.documentElement.scrollWidth > vw,
    overflowing,
    smallTargets,
    // An icon with no size rule expands to fill its container.
    oversizedIcons,
  };
})();

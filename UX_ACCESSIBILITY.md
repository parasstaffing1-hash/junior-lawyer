# Batch 27 — UX, Accessibility and Performance Polish

Batch 27 is a feature-freeze polish layer. It does not change legal conclusions or automate new areas of law.

## Accessibility foundation

- A keyboard-visible **Skip to main content** link is present on the authenticated application shell.
- `:focus-visible` has a high-visibility ring; primary navigation uses `aria-current="page"`.
- Mobile navigation is a real dismissible drawer rather than a permanently hidden sidebar.
- Coarse-pointer/mobile controls use a 44px target floor where practical.
- User-selectable high contrast, reduced motion and four text-size levels are applied at the document root.
- `prefers-reduced-motion` is respected unless the user explicitly chooses full motion.
- Keyboard help is available with `?`; universal search remains `Ctrl/Cmd + K` and traps focus while open.
- Error, loading and not-found states are explicit and do not imply that a failed screen changed legal data.

This is a strong accessibility baseline, **not a claim of formal WCAG certification**. Batch 28 should include automated and manual testing with keyboard-only navigation, screen readers and real mobile devices before a production accessibility claim is made.

## Hindi / English presentation

The global shell can be displayed in English, Hindi, or a compact bilingual mode. Devanagari content uses a dedicated system-safe fallback stack (`Noto Sans/Serif Devanagari`, `Nirmala UI`, `Mangal`) with more generous line height. No font files are bundled.

Legal source data continues to retain its original language; the display-language setting does not translate or alter source evidence.

## Large-document reader

`/documents/{document_id}` provides a page-window reader rather than loading a full extracted document into the browser.

- Default window: 8 pages (user configurable, 2–30)
- Reader zoom: 75–175%
- Find-in-document returns matching page snippets server-side
- Next/previous navigation fetches only the next bounded page window
- Search results now deep-link directly to the document reader and matching page
- Reader preserves existing document/matter permission checks

This improves browser memory use for very large case files while keeping the original files immutable.

## First-run onboarding

`/onboarding` provides five short optional steps covering preferences, first matter, first document, universal search and keyboard navigation. Progress is stored per firm membership when authentication is enabled; local display preferences remain usable during unauthenticated development.

## Persistent preferences

Batch 27 adds:

- `user_experience_preferences`
- `user_onboarding_progress`

Preferences cover interface language, density, contrast, font scale, reduced motion, keyboard hints, document page-window size, reader text zoom and last-workspace preference.

## RC1 assistive-technology gate

Batch 28 adds Playwright browser specifications for keyboard/dialog and large-document behavior. These automated checks supplement but do not replace the required manual keyboard and screen-reader pass in the RC validation campaign. Formal WCAG certification is still not claimed.

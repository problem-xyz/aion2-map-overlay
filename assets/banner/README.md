# Advertising banner

The panel shows one banner between the donation tiles and the links, when this folder has one.
It ships with the app: the app makes no network request to show it, and a new banner reaches
users with the next release. This README stays in the repository and is not part of the build.

## Adding or changing the banner

1. Put the image here: PNG, JPEG or WebP, at most 1 MB. It is drawn at the panel's full width,
   524 px at a desktop scale of 100%, and keeps its own proportions up to 160 px high; a taller
   one is cut to its middle. 1048 × 200 looks sharp on a 200% screen.
2. Add `banner.json` beside it:

   ```json
   {
     "image": "banner.webp",
     "url": "https://example.com/",
     "label": "What the banner advertises, for screen readers and the tooltip"
   }
   ```

   `url` must be https. The app opens that exact address when the banner is clicked, and no
   other address on its site.

   For a discount code, add `"promo": {"code": "…", "discount": "30%"}`. The panel then shows
   a line under the banner with the code and a Copy button. Both fields are short texts, at most
   32 characters.
3. Run `uv run pytest tests/store/test_banner.py`. A banner.json that does not check out is
   only logged, and the panel then shows no banner, so the test is what catches a typo.
4. Add a `CHANGELOG.md` entry under `[Unreleased]`.

To remove the banner, delete `banner.json` and the image.

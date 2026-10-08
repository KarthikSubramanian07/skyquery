# Privacy policy

SkyQuery is built so that there is very little to say here, and that is deliberate. This page covers both the SkyQuery software and this website.

## The SkyQuery software

- **No telemetry.** SkyQuery does not collect usage statistics, crash reports, or analytics of any kind, and it never phones home.
- **Local data stays local.** The on-disk cache, downloaded files, and the SQLite query and citation log live in a directory on your own machine (by default `~/.local/share/skyquery`, or the path in `SKYQUERY_HOME`). You can delete it at any time.
- **Keys stay in your keychain.** Optional API keys for NASA ADS and NASA Open APIs are stored only in your operating system's keychain through `keyring`. They are never written to a file, a log line, or the repository.
- **Third-party services.** In live mode, SkyQuery sends your queries directly from your computer to the public services you ask about, such as SIMBAD, JPL Horizons, VizieR, Gaia, NASA ADS, arXiv, and MAST. Those requests are governed by each provider's own privacy policy. In the default replay mode, no network requests are made at all.

## This website

- **No cookies, no tracking.** This site sets no cookies and runs no analytics or advertising scripts.
- **Local preference only.** If you switch between light and dark themes, that choice is saved in your browser's local storage and never leaves your device.
- **Hosting.** The site is served by Cloudflare Pages. Cloudflare processes standard request data such as IP addresses to deliver and protect the site, as described in the [Cloudflare privacy policy](https://www.cloudflare.com/privacypolicy/).
- **Fonts.** Typefaces load from Google Fonts, which receives a standard request from your browser.

## Contact

Questions about privacy can go to the maintainer through the channels on the [contact page](/contact).

Last updated: 2026-10-08.

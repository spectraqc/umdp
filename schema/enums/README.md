# Controlled vocabularies

Recommended-but-not-required identifier lists for fields that benefit from interoperability across profiles. The main UMDP schema (`../umdp.schema.json`) does not enforce these — adopters may extend them — but using a known identifier where one exists makes profiles diff cleanly across vendors.

| File                     | Covers                                                  |
|--------------------------|---------------------------------------------------------|
| `codecs.json`            | Video and audio codec identifiers used in profiles      |
| `containers.json`        | Container / wrapper identifiers (mxf, mov, mp4, etc.)   |
| `color.json`             | Colour primaries, transfer functions, matrix coefficients |
| `layouts.json`           | Audio channel-layout identifiers (`L-R`, `L-R-C-LFE-Ls-Rs`, …) in EBU R123 order |
| `broadcast-systems.json` | Broadcast-system / raster identifiers (`1080i/25`, `1080p/50`, …) |

Submitting a new identifier? Open a PR adding to the relevant list with a one-line description and the spec citation that uses it.

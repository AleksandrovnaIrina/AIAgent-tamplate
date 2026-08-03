> © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — see [LICENSE](../../LICENSE) / [NOTICE](../../NOTICE). Not for redistribution or reuse without permission.

# quote_card_story

Story-format quote card (1080×1920). Large serif quote centred vertically, decorative quote mark at top, author block at bottom.

## Variables

- `quote` *(required)* — the quote text, 1–3 sentences
- `eyebrow` *(optional)* — small uppercase label above the quote mark
- `author` *(optional)* — uppercase tag at the bottom
- `handle` *(optional)* — @-handle or attribution, low-opacity
- `background_color` *(optional, default "#f4ede0")*
- `text_color` *(optional, default "#1a1a1a")*
- `accent_color` *(optional, default "#c97b4b")*

## Usage

Pass `width=1080, height=1920` to render_banner.

## Example

```json
{
  "quote": "Перший рік у LinkedIn — це не про охоплення, це про послідовність.",
  "author": "Ірина — Head of HR",
  "eyebrow": "HR думки"
}
```

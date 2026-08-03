> © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — see [LICENSE](../../LICENSE) / [NOTICE](../../NOTICE). Not for redistribution or reuse without permission.

# cta_card

Warm gradient CTA card — carousel finale. Structure: badge → headline → subline → italic CTA with arrow.

## Variables

- `title` *(required)* — large serif headline
- `cta_text` *(required)* — italic call-to-action line (e.g. "гайд у профілі")
- `badge` *(optional)* — small pill label (e.g. "FREE GUIDE")
- `subline` *(optional)* — descriptive paragraph beneath the title
- `handle` *(optional)* — small text below the CTA
- `gradient_from` *(optional, default "#fce6c4")* — top-left gradient color
- `gradient_to` *(optional, default "#f0a060")* — bottom-right gradient color
- `text_color` *(optional, default "#1a1a1a")* — text color

## Example

```json
{
  "badge": "FREE GUIDE",
  "title": "Як перетворити пост на лід-магніт",
  "subline": "5 кроків + готовий чеклист",
  "cta_text": "гайд у профілі",
  "handle": "@my.brand"
}
```

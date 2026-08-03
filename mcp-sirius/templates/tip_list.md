> © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — see [LICENSE](../../LICENSE) / [NOTICE](../../NOTICE). Not for redistribution or reuse without permission.

# tip_list

Dark editorial list card with numbered tips (01, 02, 03…). Ideal for "X mistakes I made", "Y things I learned" style content for LinkedIn or Instagram carousels.

## Variables

- `title` *(required)* — large headline at top
- `tips` *(required)* — list of 3–7 strings, one per item
- `eyebrow` *(optional)* — small uppercase tag above title (e.g. "MISTAKES" / "LESSONS")
- `footer` *(optional)* — small text bottom-left
- `handle` *(optional)* — small text bottom-right
- `background_color` *(optional, default "#0f0f0f")* — page background
- `text_color` *(optional, default "#f5f5f5")* — body text color
- `accent_color` *(optional, default "#f0a060")* — numbering color

## Example

```json
{
  "eyebrow": "MISTAKES",
  "title": "3 помилки в перший рік LinkedIn",
  "tips": [
    "Постила без стратегії — і дивувалась що нема росту.",
    "Боялась повторювати теми, які заходили.",
    "Чекала ідеального тексту замість того щоб публікувати."
  ],
  "footer": "more →",
  "handle": "@my.brand"
}
```

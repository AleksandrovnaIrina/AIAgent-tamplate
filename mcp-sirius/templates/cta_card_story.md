> © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — see [LICENSE](../../LICENSE) / [NOTICE](../../NOTICE). Not for redistribution or reuse without permission.

# cta_card_story

Story-format CTA card (1080×1920). Gradient background, bold headline at top, optional detail block in the centre, CTA at the bottom.

## Variables

- `title` *(required)* — main headline
- `cta_text` *(required)* — call-to-action phrase (arrow added automatically)
- `badge` *(optional)* — dark pill label at the very top
- `subline` *(optional)* — subtitle below the headline
- `detail` *(optional)* — extra body text in the middle section
- `handle` *(optional)* — @-handle below the CTA
- `gradient_from` *(optional, default "#fce6c4")*
- `gradient_to` *(optional, default "#e07830")*
- `text_color` *(optional, default "#1a1a1a")*

## Usage

Pass `width=1080, height=1920` to render_banner.

## Example

```json
{
  "badge": "Безкоштовно",
  "title": "Чеклист для першого тижня Head of HR",
  "subline": "32 пункти. Жодної води.",
  "cta_text": "Збережи собі",
  "detail": "Що перевірити, що налаштувати і з ким поговорити в перший тиждень на новій посаді."
}
```

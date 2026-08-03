> © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — see [LICENSE](../../LICENSE) / [NOTICE](../../NOTICE). Not for redistribution or reuse without permission.

# tip_list_story

Story-format tip list (1080×1920). Coloured header block with title, numbered tips on dark background.

## Variables

- `title` *(required)* — list headline
- `tips` *(required)* — array of tip strings (3–6 recommended)
- `eyebrow` *(optional)* — small label above the title in the header
- `footer` *(optional)* — left-side footer text
- `handle` *(optional)* — right-side @-handle
- `background_color` *(optional, default "#0f0f0f")*
- `text_color` *(optional, default "#f5f5f5")*
- `accent_color` *(optional, default "#f0a060")* — header background + counter color

## Usage

Pass `width=1080, height=1920` to render_banner.

## Example

```json
{
  "title": "5 помилок рекрутера на співбесіді",
  "eyebrow": "Рекрутинг",
  "tips": [
    "Говорить більше ніж кандидат",
    "Не пояснює що далі після інтерв'ю",
    "Не читає резюме до зустрічі",
    "Задає питання зі списку без адаптації",
    "Не дає зворотний зв'язок"
  ]
}
```

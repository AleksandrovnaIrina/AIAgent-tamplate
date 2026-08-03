> © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — see [LICENSE](../../LICENSE) / [NOTICE](../../NOTICE). Not for redistribution or reuse without permission.

# checklist

Branded A4 checklist PDF with printable checkboxes. Supports flat list or grouped sections.

## Variables

- `title` *(required)* — checklist title
- `label` *(optional)* — small uppercase label above the title
- `description` *(optional)* — subtitle/description
- `author` *(optional)* — footer left
- `footer_text` *(optional)* — footer right
- `accent_color` *(optional, default "#c97b4b")*
- Use **either**:
  - `items` — flat list of strings
  - `sections` — list of `{heading, items: []}` for grouped checklist

## Example (grouped)

```json
{
  "title": "Перший тиждень Head of HR",
  "label": "Чеклист",
  "description": "Що зробити в перші 7 днів на новій позиції",
  "author": "Ірина — Head of HR",
  "accent_color": "#c97b4b",
  "sections": [
    {
      "heading": "День 1–2: Орієнтація",
      "items": [
        "Познайомитись з командою особисто",
        "Отримати доступи до всіх систем",
        "Дізнатись про поточні відкриті вакансії"
      ]
    },
    {
      "heading": "День 3–5: Аудит",
      "items": [
        "Переглянути поточні HR-процеси",
        "Зустрітись з CEO / засновником",
        "Зібрати зворотний зв'язок від команди"
      ]
    }
  ]
}
```

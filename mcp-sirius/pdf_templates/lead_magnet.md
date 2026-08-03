> © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — see [LICENSE](../../LICENSE) / [NOTICE](../../NOTICE). Not for redistribution or reuse without permission.

# lead_magnet

Branded A4 PDF lead magnet: cover page + content sections. Great for guides, frameworks, strategy docs.

## Variables

- `title` *(required)* — main title on the cover
- `sections` *(required)* — list of `{heading, body}` objects. `body` is plain text (newlines preserved).
- `eyebrow` *(optional)* — small uppercase label above the title on cover
- `subtitle` *(optional)* — subtitle on the cover
- `author` *(optional)* — shown on cover footer and doc footer
- `footer_text` *(optional)* — right-side footer text on content pages
- `accent_color` *(optional, default "#c97b4b")* — cover background + headings

## Example

```json
{
  "title": "5 помилок рекрутера на співбесіді",
  "eyebrow": "Гайд",
  "subtitle": "І як їх не повторити наступного разу",
  "author": "Ірина — Head of HR",
  "accent_color": "#c97b4b",
  "sections": [
    {
      "heading": "Говорить більше ніж кандидат",
      "body": "Якщо рекрутер заповнює 60% часу розмови — це не інтерв'ю, це монолог.\n\nКандидат не може показати себе. Рекрутер не отримує інформацію.\n\nПравило просте: ти питаєш, вони говорять."
    },
    {
      "heading": "Не пояснює наступні кроки",
      "body": "Кандидат виходить з кімнати і не знає: коли відповідь? Хто напише? Що далі?\n\nЦе не дрібниця — це повага до людини і до процесу."
    }
  ],
  "footer_text": "2026 · Sirius Content"
}
```

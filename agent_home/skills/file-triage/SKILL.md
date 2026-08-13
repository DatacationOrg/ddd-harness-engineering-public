---
name: file-triage
description: Northwind Freight's rules for naming, filing and archiving documents. Use whenever organising, renaming, moving, archiving or de-duplicating files, or when deciding where a new document belongs.
allowed-tools: ls, glob, grep, read_file, write_file
---

# Filing rules for Northwind Freight

These are the house rules. Apply them without being asked; they are why the
folder structure looks the way it does.

## Naming

Every filed document is named:

```
<YYYY-MM-DD>_<type>_<counterparty>_<reference>.<ext>
```

- Dates are ISO, always. `2026-03-04`, never `04-03-26`.
- `<type>` is one of: `invoice`, `bol` (bill of lading), `pod` (proof of
  delivery), `quote`, `contract`, `report`, `photo`.
- `<counterparty>` is the client or carrier in `PascalCase`, no spaces:
  `BergmannLogistik`.
- `<reference>` is their document number if one exists, else `na`.

Correct: `2026-03-04_invoice_BergmannLogistik_INV-2025-0842.pdf`

Never: `invoice final v2.pdf`, `Copy of INV-2025-0842.pdf`, `IMG_4471.jpg`

## Where things go

| Content | Destination |
|---|---|
| Anything about a specific client | `Clients/<CounterpartyName>/` |
| Invoices in or out | `Invoices/<YYYY>/` |
| Shipment data, exports, CSVs | `data/` |
| Anything older than two years | `archive/<YYYY>/` |
| Anything you produce yourself | `workspace/` |

## Duplicates

Compare **contents**, never names. Files with near-identical names are usually
genuinely different versions, and files with unrelated names are often
byte-identical copies.

When you find true duplicates:

1. Keep the copy already in the correct location under the correct name.
2. If none is correctly located, keep the oldest and rename it properly.
3. List the redundant copies for a human to confirm. **Do not delete anything.**

## Rules that override convenience

- **Never delete.** Propose deletions; let a human execute them.
- **Never move a file out of `Clients/`** without saying which client it belongs
  to and why.
- **Credentials, keys and anything that looks like a secret are never copied,
  never summarised, and never included in a report.** Note that the file exists
  and move on.
- If a file's correct destination is ambiguous, leave it and say so. A wrong
  confident filing costs more to undo than an unfiled document.

## Reporting

When you finish a triage pass, write a short summary to
`workspace/TRIAGE.md`: what you moved, what you renamed, what you propose
deleting, and what you could not classify. Counts, not a full listing.

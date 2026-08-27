# Biella Engine — Corporate Asset List

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Date: 2026-08-27  
Scope: Biella Engine corporate/business brand applications

## 1. Purpose

Define the required business-facing applications of the Biella Engine identity so the brand works beyond cinematic/game presentation.

All corporate assets must derive from the same approved master geometry, colors and typography.

Corporate production must communicate:

- international business quality;
- technical credibility;
- precision engineering;
- premium restraint;
- enterprise readiness.

## 2. Required asset families

The final corporate production inventory must include:

```text
business card
letterhead
invoice
quotation
email signature
proposal cover
report cover
presentation cover
signage
website treatments
```

Recommended supporting templates:

```text
document header/footer
meeting one-pager
company profile cover
case-study cover
partner/enterprise sheet
social/company profile header
favicon/app-linked corporate mark
```

## 3. Business card

Required layouts:

```text
front brand side
back contact side
```

Requirements:
- standard regional print size chosen and documented;
- print-safe bleed;
- CMYK proof;
- vector logo;
- one-color fallback;
- no unnecessary cinematic FX;
- contact fields remain editable;
- no raster-only logo.

Suggested information hierarchy:

```text
name
role/title
email
phone if used
website
company
```

Use actual approved business/contact data only at final production.

## 4. Letterhead

Required:
- A4 master;
- US Letter derivative if international usage requires it.

Components:
- logo/wordmark;
- company/contact footer or header;
- editable body area;
- optional subtle brand line/pattern.

Rules:
- high print clarity;
- no dark full-page background for default stationery;
- monochrome-compatible print variant.

## 5. Invoice

Required editable template with:

```text
company identity
invoice number
date
billing details
line items
subtotal
tax
total
payment/reference section
footer
```

This file defines visual structure only. Legal/tax/business fields must be finalized from actual company requirements and jurisdiction; do not invent them.

Branding:
- clean;
- restrained violet accents;
- printable in grayscale;
- strong numeric/table readability.

## 6. Quotation

Required editable template with:

```text
quotation number
date
client
scope/items
quantity/rate
subtotal
tax/adjustments
total
validity/terms area
approval/contact area
```

Do not copy legal/payment language from invoice without explicit business approval.

## 7. Email signature

Required:

```text
rich HTML-compatible signature
plain-text fallback guidance
```

Visual elements:
- name;
- role;
- Biella Engine;
- website;
- approved contact channels;
- small logo/mark where email client constraints permit.

Rules:
- lightweight;
- no giant banners;
- no animated logo by default;
- no remote tracking asset requirement in the brand master;
- readable when images are blocked.

## 8. Proposal cover

Required variants:

```text
dark premium
light corporate
```

Fields:
- proposal title;
- client/project;
- date;
- Biella Engine identity;
- optional confidentiality/status label if actually required.

Visual:
- master logo;
- controlled engineering pattern/material;
- no excessive game-poster FX.

## 9. Report cover

Required:
- technical report;
- business/management report.

Fields:
- report title;
- subtitle;
- date/version;
- author/team;
- company identity.

Must support long technical titles without breaking layout.

## 10. Presentation cover

Required:
- 16:9 presentation cover;
- title/content-slide branding system may be added later.

Cover elements:
- logo/wordmark;
- title;
- subtitle;
- date/presenter;
- premium dark or light treatment.

Cinematic imagery may be used on special presentations, but a clean corporate cover is mandatory.

## 11. Signage

Required use cases:

```text
office wall / reception
event booth
wayfinding brand plaque
digital signage
large-format banner
```

Requirements:
- vector master;
- clear-space rules;
- monochrome option;
- no dependence on glow;
- scalable from small plaque to large-format print.

Physical manufacturing variants consume `PHYSICAL_APPLICATION_LIST.md`.

## 12. Website treatments

Corporate website asset requirements:

```text
header wordmark / mark
footer mark
favicon/app icon
social share card
company/about hero treatment
contact/business surface treatment
dark-background logo
light-background logo
monochrome fallback
```

Website implementation remains a project consumer of brand assets; these files do not define the website architecture.

## 13. Color usage

Corporate default:

- deep navy/graphite;
- polished silver/warm white;
- Biella violet accent.

Heat orange:
- generally excluded from routine corporate documents;
- may appear only in approved cinematic/industrial imagery.

Corporate documents must remain credible in grayscale/one-color printing.

## 14. Typography

Consume `TYPOGRAPHY_SPEC.md`.

Requirements:
- business-document readability;
- stable heading/body hierarchy;
- licensed font usage;
- fallback fonts documented;
- editable live text in source;
- no rasterized body copy.

## 15. Logo usage

Corporate assets consume:

```text
MASTER_LOGO_GEOMETRY.svg
approved wordmark
approved horizontal/stacked lockups
monochrome variants
```

Until the master geometry exists, no approximation may become the authoritative corporate logo source.

## 16. File formats

Editable source depends on application/tool actually used and must be retained.

Final delivery as applicable:

```text
PDF
SVG
PNG
JPG preview
editable office/design source
HTML for email signature
```

Print PDFs:
- vector logo preserved;
- fonts embedded/outlined as required;
- CMYK proof derived from approved color management;
- bleed/crop marks only where needed.

## 17. Naming examples

```text
BIELLA_ENGINE_BUSINESS_CARD_MASTER_v001.pdf
BIELLA_ENGINE_LETTERHEAD_A4_MASTER_v001.pdf
BIELLA_ENGINE_INVOICE_MASTER_v001.pdf
BIELLA_ENGINE_QUOTATION_MASTER_v001.pdf
BIELLA_ENGINE_EMAIL_SIGNATURE_MASTER_v001.html
BIELLA_ENGINE_PROPOSAL_COVER_DARK_v001.pdf
BIELLA_ENGINE_REPORT_COVER_LIGHT_v001.pdf
BIELLA_ENGINE_PRESENTATION_COVER_16X9_v001.png
BIELLA_ENGINE_SIGNAGE_MONO_PRINT_v001.pdf
BIELLA_ENGINE_SOCIAL_SHARE_WEB_v001.png
```

## 18. Editable-field rule

Business data must remain editable in templates.

Do not bake into master templates:
- person names;
- client names;
- prices;
- invoice numbers;
- dates;
- addresses not yet approved;
- legal text not supplied by the business;
- bank/tax details.

Use documented placeholder field labels only in template source; final exported production files must contain real approved data or be clearly identified as templates.

## 19. Physical / print quality

For print applications:

- vector-first logo;
- 300 ppi raster imagery minimum at placed size;
- correct bleed;
- overprint/black handling reviewed where relevant;
- CMYK proof;
- one-color proof.

Metallic appearance in print may be simulated as a derived design effect, but the core mark must remain valid without it.

## 20. Delivery structure

Recommended:

```text
09_CORPORATE/
|-- CORPORATE_ASSET_LIST.md
|-- SOURCE/
|   |-- BUSINESS_CARD/
|   |-- LETTERHEAD/
|   |-- INVOICE/
|   |-- QUOTATION/
|   |-- EMAIL_SIGNATURE/
|   |-- PROPOSAL/
|   |-- REPORT/
|   |-- PRESENTATION/
|   |-- SIGNAGE/
|   `-- WEBSITE/
`-- EXPORTS/
    |-- PDF/
    |-- SVG/
    |-- PNG/
    |-- HTML/
    `-- PRINT/
```

## 21. QA per corporate asset

Verify:

- master logo is correct;
- typography licensed/available;
- editable source exists;
- live text remains editable where appropriate;
- output opens correctly;
- print dimensions correct;
- bleed correct where required;
- colors match role;
- one-color fallback exists where required;
- no placeholder/fake business data in approved final output;
- no missing linked assets;
- filename follows standard;
- manifest/export-matrix entry exists.

## 22. Completion rule

This list defines required corporate production scope.

The corporate asset package is not complete merely because this control document exists. Completion requires actual editable templates, validated exports and QA evidence for the required applications.

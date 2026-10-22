---
id: T-0018
title: Fix the Certum certificate not added to the profile
tier: business
project: axon-poland
priority: P1
status: new
due: null
week: null
pinned: false
weeks: []
repeat: null
repeat_until: null
series: null
created: 2026-10-19T12:32:04+02:00
updated: 2026-10-19T12:32:04+02:00
closed: null
source: text
---

## Description

There is a problem with the electronic signature for Axon Poland: Certum is not adding the user's certificate to the profile. Resolve this as soon as possible. Done when the certificate appears in the profile and a document can be signed with it.

## Additional information

- Place: Certum (Asseco Data Systems) support — hotline +48 91 4801300, email infolinia@certum.pl, chat and contact form on the site. Consultants are available Monday to Friday, 8:00–16:00 CET, which is the same time zone as Omegna. — [source](https://www.certum.eu/en/contact/), 2026-10-19
- Research: For a cloud (SimplySign) certificate, Certum says the user must be logged in to the SimplySign Desktop app, which works as a virtual smart card. For a physical card, an empty certificate list usually means proCertum CardManager is out of date, and a new card's common profile must first be initialized (PIN and PUK set) in CardManager. — [source](https://support.certum.eu/en/simplysign-activation-of-certificate-renewal/), 2026-10-19
- Research: When contacting support, say whether the certificate is cloud-based (SimplySign) or on a physical card, and give the operating system and app version. — [source](https://files.certum.eu/documents/manual_en/SimplySign_activation_of_certificate_renewal_en_v_1.2.pdf), 2026-10-19

## Original input

> We have a problem with electronic signature. Certum is not adding my certification to the profile. We need to resolve this as soon as possible. It's regarding Axon Poland.

---
title: "What's New in Hindsight Cloud: Going Global"
authors: [benfrank241]
date: 2026-05-15T12:00
tags: [hindsight-cloud, release, i18n, internationalization, billing]
description: "Hindsight Cloud now speaks 8 languages and accepts Alipay at checkout — plus a quieter set of billing and reliability upgrades shipped over the past six weeks."
image: /img/blog/hindsight-cloud-goes-global.png
hide_table_of_contents: true
---

<!-- TODO: replace placeholder hero image before merge -->

Most of what we've shipped to Hindsight Cloud since the last update is about the same thing from different angles: making the product feel native no matter where you're using it from. The UI in eight languages, payments that route through whatever rails your country actually uses, and user docs that don't force you back into English to figure out how memory banks work.

<!-- truncate -->

- [**The UI in 8 languages**](#the-ui-in-8-languages) — full localization via a language picker in the nav.
- [**Pay how you actually pay**](#pay-how-you-actually-pay) — Alipay alongside card at checkout.

## The UI in 8 languages

The Cloud UI is now fully internationalized across **English, Spanish, French, German, Portuguese, Japanese, Korean, and Chinese (Simplified)**. There's a language picker in the nav; pick one and every page, every component, every modal, every toast switches over.

This wasn't a `t('signup.button')` veneer over the obvious copy. Bank views, entity graphs, consolidation progress UI, failed-operation dialogs, the support chat widget, even the canvas-drawn text in the 2D graph and constellation views — all of it goes through the i18n layer. Roughly 3,000 keys across 70 namespaces, with every locale at full parity (no English fall-through, no missing keys).

Plurals and interpolation are ICU MessageFormat-correct, which matters more than it sounds — getting "1 memory" vs "2 memories" right in Japanese or Russian without hand-coded fallbacks.

If you spot a translation that reads wrong in context, please [open an issue](https://github.com/vectorize-io/hindsight/issues/new) — getting the *technical* tone right (vs. literal-but-awkward) is where machine translation routinely loses, and we'd rather hear about it than ship through it.

Our user docs are also now available in **Simplified Chinese**, so the documentation matches the UI for our Chinese customers without a context-switch into English.

## Pay how you actually pay

Hindsight Cloud's Stripe checkout used to be card-only, regardless of where you were buying from. For Chinese customers, that was a real problem: a large share of consumer payments in China run through Alipay, not card. We were watching ~15% Stripe completion rates for users with Chinese-domain emails against ~42% for everyone else.

Checkout now surfaces **Alipay alongside card** for customers whose Stripe-detected billing location supports it. You don't have to configure anything; it just shows up at checkout. The same goes for any other region-specific payment method we enable in the Stripe Dashboard going forward — Stripe's `automatic_payment_methods` picks the right rails based on your country and currency.

One caveat worth being explicit about: **auto-recharge is still card-only**, because Alipay is a single-use method Stripe can't save off-session. If you want auto-recharge enabled, you'll need a card on file via the "Add payment method" flow on the billing page; one-off Alipay purchases work fine but won't enroll you in auto-recharge by themselves.

## What else shipped

A few other things landed during the same window that aren't part of the i18n theme but are worth mentioning:

- **Auto-recharge v2 and checkout recovery.** The auto-recharge logic now has per-org daily caps, race protection, and exponential-backoff retries when a charge fails for insufficient funds. If you abandon a credit-purchase checkout, you'll get a recovery email with a link that drops you back into the same session — most of the time, the friction of starting over was the reason the purchase didn't complete. Post-purchase, auto-recharge is now opt-in default-on (one click to turn it off if you don't want it).
- **Quieter dashboards.** Low-balance email nudges, a credit-exhausted operations card on the dashboard, and audit logging for Stripe purchase failures so card declines don't go silent anymore.
- **Reliability under load.** Worker pools now scale on KEDA against actual claimable-task depth (rather than wall-clock cron), and Postgres runs in CNPG with three instances and replication slots in production. None of this is user-facing, but recall latency under heavy multi-tenant load is materially better than it was six weeks ago.

## Try it

Hindsight Cloud is the easiest way to run Hindsight without operating it yourself — managed Postgres, OAuth for MCP clients, billing, multi-org, and now eight languages.

[Sign up at ui.hindsight.vectorize.io/signup](https://ui.hindsight.vectorize.io/signup) — the free tier is enough to try retain and recall against a real bank without entering a card.

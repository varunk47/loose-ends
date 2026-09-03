# Loose Ends or Status: the pick

Decision memo for the Agents for Humans team. Research date Sep 1 to 2, 2026. Companion files: `loose-ends-project-spec-v2.md` (the improved spec, read the "what changed" block first) and `status-project-spec.md` (the immigration idea written to the same depth).

## Verdict

**Build Loose Ends.** Death admin is the only one of the two that passes your own bar, "it should not exist anywhere else", and it is the better fit for how AWS judges have actually scored past hackathons.

Status is a good idea with a great "why now" (the duration-of-status rule lands Sep 15, the day after the deadline). It loses on uniqueness, on end-to-end execution, and on demo-ability. If someone on the team lived through OPT and feels strongly, section 6 says what would have to be true to make it win anyway.

## The uniqueness test

| | Loose Ends | Status |
|---|---|---|
| Commercial products | Elayne (closest, 6/10), Sunset (5/10), Alix, Empathy, EverSettled. All financial-aggregation or human staff. None parse the deceased's inbox, none make calls, none run on a schedule with a digest. | TrackMyOPT and VisaBuddy (6/10 each) already track OPT and H-1B clocks with reminders. Lawfully has 2.5M+ users polling USCIS. Boundless prefills forms for employers (7/10, wrong audience). |
| Prior hackathon projects | None. Devpost, lablab.ai and GitHub turned up only blockchain inheritance tools and pre-death dead-man's-switch vaults. | VisaPath (Devpost, Feb 2026): an F-1 timeline guardian with 56 USCIS rules and RAG, built by an F-1 student. Plus GeoNext, GreenGo, LlamaLaw and five single-purpose USCIS pollers on GitHub. |
| In-flight signal for this hackathon | Zero mentions across Reddit, X, LinkedIn, Medium, dev.to, builder.aws. | Same zero, but 6,841 registrants skew toward the exact population that scratches this itch. Expect duplicates. |
| Verdict | Unclaimed lane. | Partially exists; the combination is novel, the category is not. |

The two agents' full tables are in the spec files. The line to remember: nobody found combines inbox discovery, autonomous email plus form plus voice execution, and a decision digest; for immigration, the deadline-tracking core is commoditized and a judge could name a prior Devpost entry.

## Head-to-head on the five equally weighted criteria

Scores are my estimates of how each idea can land in 13 days with 4 people, not measurements.

| Criterion | Loose Ends | Status | Why |
|---|---|---|---|
| Technical implementation | 5 | 3.5 | Loose Ends shows Graph, agents-as-tools, HumanInTheLoop with deferred asks, BidiAgent voice, AgentCore Browser, Memory, two runtimes. Status cannot touch SEVIS or USCIS (no API a student can use), so its agent prepares and drafts; the "end to end" the brief asks for stops at the human. |
| Design | 4 | 4.5 | Status is simpler and will polish better. Loose Ends has more surfaces to get right. |
| Potential impact | 4.5 | 4 | 3.1M US deaths a year, 20 months per executor, every judge has a relative. Status has 1.8M principals and existential stakes, but a narrower audience. |
| Creativity and originality | 5 | 3 | Verified unclaimed vs. a category with a prior Devpost entry and consumer apps at scale. |
| Presentation | 4.5 | 3.5 | A phone call closing a dead man's gas account is a moment. Pre-filled PDFs and drafted emails are not. |
| Total | 23 | 18.5 | |

## What past AWS hackathon winners tell us

- Admin-paperwork agents win, they are not consolation prizes: AegisAgent (insurance claims) and Province (auto-fills Form 1040) placed top-3 in the 2025 AWS AI Agent Global Hackathon.
- Winners lead with a hard number and show multiple specialized sub-agents, not a chatbot with tools.
- Browser and computer-use automation is a proven wedge (Nova Act category winner, "Sai" in the Nova hackathon). Voice places consistently where it exists.
- Live end-to-end demos and AgentCore deployment are explicitly weighted in this hackathon's rules.
- AWS is recycling six example ideas across Resources and Updates: bill tracking, return windows, household calendars, teacher materials, food-bank shifts, nonprofit Q&A. Expect heavy clustering there. Neither of our ideas is on that list.
- An AWS advocate (Brooke Jamieson) posted "10 ideas for the Agents for Humans hackathon" on Threads. Someone should read it today to confirm death admin is not on it.

## Risks that could still sink Loose Ends, and the fix in v2

| Risk | Fix |
|---|---|
| v1 scope: 9 agents, 2 runtimes, 3 mailbox adapters, Cognito, voice and browser all in the MVP | v2 cuts the MVP to one perfect loop. Voice is recorded by Sep 9 or becomes a slide. |
| "You need the dead person's email password" | v2 adds mail-pile photos and a statement PDF as discovery channels. The demo shows two accounts found only from envelopes. |
| A judge says "Alix already does this" | v2 section 4 has the verbatim answers: Alix and Empathy are human specialists with AI assist; Elayne is financial aggregation with humans on the phone; SubCaddy cannot act on a deceased person's accounts. |
| Feels like a checklist app with an LLM | Three features nobody has: Ghost Watch (post-death identity-theft and zombie-billing monitoring), Money Recovered counter, Vendor Memory that learns each vendor's real procedure from replies. |
| Voice flakiness on demo day | Nova 2 Sonic connections cap at 8 minutes; keep calls short; record early; email path stays primary in the video. |
| Model access delays | Sonnet 5 needs a Marketplace agreement on Bedrock. Start on Sonnet 4.6, swap the ID later. Everything in us-east-1. |

## If you pick Status anyway

Only do it if all of these are true:

1. Someone on the team lived through OPT or H-1B and will narrate the video. Without that, it reads as researched, not lived.
2. You lead every pitch with the inbox-to-form loop (offer letter arrives, I-983 pre-filled, DSO email drafted) and never with the clock board, because the clock board is what TrackMyOPT sells.
3. You never say "nothing like this exists". Say "nobody reads the email that starts the clock".
4. Dates come from a tested rules engine with version switching, and the Sep 15 rule is the demo of why.
5. You accept that AWS may be less eager to feature an immigration-compliance tool in a social post, which is part of the grand prize.

The full spec is in `status-project-spec.md` if that is the call.

## What changed in the two specs

- `loose-ends-project-spec-v2.md`: scope cut to one loop, three discovery channels, Ghost Watch, Money Recovered, Vendor Memory, authority packet, pause button, rewritten competitive section with judge rebuttals, evidence refreshed (CDC 2025, Empathy Grief Tax 2025), every Strands and AgentCore claim verified against current docs with corrections inline, voice hard-dated.
- `status-project-spec.md`: new. Clock registry with rule versions, the Sep 15 fixed-admission rule, feasibility findings on USCIS and SEVIS access, competitor table, demo script, data model, guardrails.

## Sources

Hackathon: https://agentsforhumans.devpost.com and /rules and /resources. Prior winners: https://aws-agent-hackathon.devpost.com, https://amazon-nova.devpost.com. Death-admin competitors: alix.com, hellosunset.com, elayne.com, empathy.com, goodtrust.com, eversettled.com, settld.care, subcaddy.com, zeranda.ai. Immigration competitors: trackmyopt.com, visabuddyapp.com, lawfully.com, boundless.com, developer.uscis.gov, https://devpost.com/software/visapath-d8ea6t. Rule change: https://studyinthestates.dhs.gov/final-rule-establishing-a-fixed-time-period-of-admission-and-an-extension-of-stay-procedure-faq. Population: IIE Open Doors 2025, USCIS H-1B Authorized-to-Work report, CDC VSRR No. 44. Evidence: Empathy Grief Tax 2025.

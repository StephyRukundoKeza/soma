# SOMA: 10-Day Workplan

Stephy Rukundo Keza · November 2026

## Plan
| Day | Date | Milestone | Outputs | Main risk |
|---|---|---|---|---|
| 1 | Fri 20 Nov | Problem framing | Project idea and name | Scope too broad |
| 2 | Sun 22 Nov | Design decisions | Users, languages, session flow | Scope too broad |
| 3 | Mon 23 Nov | Requirements check | Requirements checklist | Missed requirements |
| 4 | Tue 24 Nov | Use case, documents, extraction | use_case.md, workplan.md, extract.py, chunk.py | Scanned pages and OCR quality |
| 5 | Wed 25 Nov | Grounded answers, risks, test set | index.py, rag.py, risk_register.md, test_set.csv | Kinyarwanda search quality |
| 6 | Thu 26 Nov | Website, fluency practice, cloud and local models, Kinyarwanda speech | Live website, tutor_prompt.md | Deployment; local model speed |
| 7 | Fri 27 Nov | Mobile app with offline access, login with roles, user tests | Installable app, user_test_notes.md | Limited time |
| 8 | Sun 29 Nov | Model comparison, red-teaming, educator ratings | results.csv, redteam_log.md, rater agreement | Raters' availability |
| 9 | Mon 30 Nov | Cost estimate, handover, memo, demo script, submission | README, memo, demo_script.md, cost_latency.md | Limited time |
| 10 | Tue 1 Dec | Buffer | Final fixes | None |

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Poor OCR on scanned pages | Medium | Medium | Rely on text pages where possible and report OCR quality |
| Weak Kinyarwanda search or answers | Medium | High | Test early, compare models, and report the gap |
| Free API limits reached | Medium | Medium | Cache answers; switch to the second cloud model or the local model |
| Local model too slow on a laptop | Medium | Low | Use the smallest model and report the hardware needed |
| Kinyarwanda speech models fail to load | Medium | Medium | Test early; fall back to typed answers for Kinyarwanda |
| Educators unavailable to rate | Medium | Medium | Invite them early and accept a smaller rating set |
| Privacy of minors | Low | High | Remove names before any model call; random IDs; no stored audio (see risk_register.md) |
| Two days lost | Low | High | Follow the cut plan below |

## If two days are lost
I will cut, in this order:
1. French
2. Kiswahili
3. The Android APK (the installable web app stays)
4. The third model in the comparison

I will keep in all cases: grounded answers with page citations, English and Kinyarwanda, the website, the test set, the risk register and the memo.

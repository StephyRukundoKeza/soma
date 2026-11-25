# SOMA: Risk Register

SOMA is used by learners aged about 15-17. This register lists the main risks and how I address them.

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **Privacy:** student names, phone numbers or emails are sent to a cloud model | Medium | High | Every model call goes through one function that removes names, phone numbers and emails (tested). Students are identified by random IDs; names stay with teachers and the administrator. |
| 2 | **Privacy:** voice recordings are stored or shared | Low | High | Speech is turned into text on the device or server, then the audio is discarded. Audio is never stored or sent to a language model. |
| 3 | **Privacy:** the free cloud tier may use requests to improve the provider's models | Medium | Medium | Only questions, book passages and answer text are sent. For a school pilot, I recommend a paid tier whose terms exclude training on requests, or the local model. |
| 4 | **Wrong answers:** the AI states something incorrect | Medium | High | Answers come only from REB passages, with page citations so learners and teachers can check them. If no passage matches, SOMA says "This is not in your book." Answers are rated by educators. |
| 5 | **Cheating:** learners use SOMA to do homework or copy answers | High | Medium | Teacher's guides (which contain answer keys) are never shown to students (tested). Speaking practice gives hints before answers, and a model answer only after two attempts. |
| 6 | **Over-reliance:** learners let SOMA think for them | Medium | Medium | Hints first; learners must speak or write their own answer; SOMA points back to the book page. Teachers see progress and who is stuck. |
| 7 | **Language bias:** quality is lower in Kinyarwanda and Kiswahili than in English | High | Medium | Questions are translated for search; Kinyarwanda quality is measured and reported; Digital Umuganda's Kinyarwanda speech models are used. |
| 8 | **Speech bias:** speech recognition works worse for some accents, ages or genders | Medium | Medium | Learners can type instead of speaking. Feedback focuses on what was said, not on accent. Tested with different speakers. |
| 9 | **Harmful or off-topic use:** unsafe requests or attempts to make SOMA ignore its rules | Medium | High | Strict rules in the system prompt; off-topic questions are refused; tested with 25 adversarial prompts (see redteam_log.md). |
| 10 | **Discouragement:** corrections make shy learners feel worse | Medium | Medium | Encouraging feedback (green for what went well, yellow for "not yet", no red crosses); self-paced levels; learners compare with their own progress, never with others. |
| 11 | **Unavailability:** the cloud model is overloaded or there is no internet | High | Medium | Automatic fallback across models; a local model on a school computer; lessons work offline and feedback is queued. |

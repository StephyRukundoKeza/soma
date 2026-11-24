# SOMA: Use-Case Decision

Stephy Rukundo Keza · Digital Umuganda & IndabaX Cameroon AI for Education Fellowship · November 2026

## 1. Decision
I am building SOMA, an AI speaking coach that helps Senior 4 learners in Rwanda speak fluently, clearly and politely in Kinyarwanda, English and Kiswahili, and then French. SOMA is grounded in REB textbooks: it answers only from them and cites the page. It also supports reading. A Primary mode for P1-P3 reading skills is visible in the app and marked "in development".

## 2. Users
- **Students:** Senior 4 learners, about 15-17 years old, in all A-level combinations.
- **Teachers:** create student accounts, choose the unit, and follow class progress and common mistakes.
- **School administrator:** manages accounts and roles.

## 3. The problem
- **Little speaking practice:** a study of secondary schools in Musanze found that low English speaking proficiency comes from shyness to practise speaking, a lack of English clubs and low motivation (Nyirahabineza et al., 2024).
- **A national priority:** in 2026, MINEDUC launched the ORATOR National English Competition to improve spoken English, public speaking, leadership and critical thinking in secondary schools.
- **Reading:** in Rwanda's first PISA assessment (2025), only 3.9% of 15-year-olds reached Level 2 in reading.
- **Language of instruction:** English has been the language of instruction since 2019, while almost all learners speak Kinyarwanda at home.
- **The gap:** I found no AI tool in Rwanda that offers curriculum-grounded speaking practice in Kinyarwanda, English and Kiswahili. Efekta's AI English programme mainly trains teachers, and Chidi is a general learning companion.

## 4. How a session works (about 15 minutes)
1. The student signs in with an account created by the teacher. Lessons open offline.
2. "Today's practice" comes from the unit the class is studying.
3. **Learn:** a short card from the REB book with key phrases, audio, the page number, and an explanation in Kinyarwanda.
4. **Practise:** a scenario such as a debate, an interview or a presentation. The student speaks for about 30 seconds, or types.
5. **Feedback:** the speech is turned into text; SOMA measures fluency (words per minute, pauses, filler words, taught phrases used), finds the matching book pages, and gives feedback with a hint first. Green shows what went well and yellow means "not yet". After two tries, SOMA shows a model answer.
6. **Ask SOMA:** questions are answered only from the books, with page numbers, or SOMA says "this is not in your book".
7. **Save and sync:** progress is saved on the device and sent when online. Without internet, an attempt is queued and the feedback arrives later.

## 5. Documents
| Document | Units | Role |
|---|---|---|
| REB General Studies and Communication Skills (GSCS) S4, student book | 13 | Main book (communication) |
| REB English S4, student book (2019) | 8 | English practice |
| REB Ikinyarwanda S4, student book | 6 | Kinyarwanda practice |
| REB Kiswahili S4, student book (2022) | 5 main topics | Kiswahili practice, including dialogues and debates |
| REB Français S4, livre de l'élève (2019) | 9 | French practice |
| REB teacher's guides for the five books above | n/a | Answer keys and teaching steps |
| REB Guidance and Counselling Module 1 (2024); Education and Career Pathways in Rwanda (REB/UNICEF, 2022); REB Career Guidance and Counselling teacher's guide | n/a | Interview and career-conversation scenarios |
| *Communication in Practice* (J. Rose, University of Minnesota, 2025, CC BY 4.0) | 16 chapters | Extra source outside the REB curriculum, labelled as such |

REB books are always searched first. The PDFs are not stored in this repository; the setup guide explains where to download them.

## 6. How this meets the brief
- **At least 10 digitized chapters:** GSCS S4 has 13 units; the three main books have 27 units together.
- **Tables:** English S4 includes tables on grammar, vocabulary, careers and salaries (e.g. pp. 2, 9, 14, 18, 30), and Ikinyarwanda S4 includes grammar tables (e.g. pp. 30-31, 44-46).
- **Scanned pages:** parts of the GSCS book are scanned, so the pipeline uses OCR where needed.

## 7. Languages
Kinyarwanda and English come first, then Kiswahili, then French. Learners can ask in Kinyarwanda about English content and get the explanation in Kinyarwanda.

## 8. Models
- **Cloud:** Google Gemini Flash (main) and a large open model on Groq (comparison).
- **Local:** Gemma 3 4B through Ollama, with Tiny Aya Global as a second option, running on a laptop or a school computer and reachable over school Wi-Fi without internet.
- **Speech:** Digital Umuganda's Kinyarwanda speech-to-text and text-to-speech models; the browser's or phone's speech recognition for English, Kiswahili and French.
- The model provider is a setting, so SOMA can switch between cloud and local models.
- **Next phase:** compare with a Kinyarwanda language model once one is publicly available.

## 9. Privacy
Only the question, the book passages and the student's answer text are sent to a model, through a single function that removes names, phone numbers and emails. Students are identified by random IDs; names stay with teachers and the administrator. Audio is neither stored nor sent. For a school pilot, I recommend a paid tier or a provider whose terms exclude training on requests, or the local model.

## 10. Primary mode (in development)
SOMA's Primary mode will support P1-P3 reading: group reading on one shared PC, Kinyarwanda first, levels from sounds to passages, help that fades as learners progress, and an alert to the teacher when a child needs help. I propose it as the next pilot.

## 11. Fallback
If the language books are judged not to meet the "tables or equations" requirement, I will switch to S4 Physics or Biology and keep the speaking and Kinyarwanda features.

## 12. Beyond this prototype
This prototype was built in about ten days, alongside other commitments. The fellowship would give me the time, mentorship and expertise to take SOMA much further: testing it with learners and teachers in real classrooms, improving Kinyarwanda and Kiswahili speech and feedback with Digital Umuganda's team, completing the Primary reading mode, and evaluating whether learners' fluency actually improves over time.

I am also open to the direction the fellowship takes. If the team's priorities lead to a different use case, I will bring the same approach and the lessons from SOMA to that work: grounding in the Rwandan curriculum, putting Kinyarwanda first, designing for low connectivity, and protecting learners' privacy.

## Sources
- Nyirahabineza, Tabaro & Mugirase (2024). Causes and Remedies for Secondary School Learners' Low English Speaking Proficiency in Musanze District, Rwanda. EAJESS 5(3): https://ajol.info/index.php/eajess/article/view/279800
- REB, ORATOR National English Competition (2026): https://www.reb.gov.rw/news-detail/from-bk-arena-to-the-united-kingdom-orator-competition-opens-a-new-chapter-for-english-proficiency-rewarding-30-outstanding-students-with-an-international-leadership-experience
- The New Times, PISA results (September 2026): https://www.newtimes.co.rw/article/38846/news/education/13-things-global-pisa-results-revealed-about-rwandan-students
- AIR, BUILD Rwanda Report (March 2026): https://air.org/sites/default/files/2026-04/BUILD-Rwanda-Report-March-2026.pdf
- Efekta in Rwanda: https://www.edtechinnovationhub.com/news/efekta-expands-rwanda-ai-teacher-training-program-to-more-than-90000-participants
- REB e-learning platform: https://elearning.reb.rw

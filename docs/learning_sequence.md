# Learning sequence: disagreeing politely

I chose **disagreeing politely** as SOMA's hard concept. Senior 4 learners often know the words but freeze or sound rude when they disagree with a friend, a teacher or a leader, and speaking diplomatically is exactly the fluency SOMA is built for.

Each step builds on the one before. A learner moves on only when their own answer meets the step's pass rule.

| Step | The learner learns to… | Passes when… | English book pages |
|---|---|---|---|
| 1. Listen before you answer | show they heard the other person first | they sum up the other person's point before reacting | GSCS S4, p. 12 |
| 2. Accept what is right in their view | name what makes sense in the other view | they name one good point in it | Communication in Practice, PDF p. 227 (outside the REB curriculum) |
| 3. Soften your words | use could, would, I think, please | they disagree with at least one softener and no rude words | English S4, PDF p. 71–72 |
| 4. Disagree with the idea, not the person | give a reason without belittling anyone | they give a reason and do not attack the person | GSCS S4, p. 28 and p. 38 |
| 5. Formal or informal? | fit the tone to the listener | the tone fits a teacher or a friend | English S4, PDF p. 72 |
| 6. Put it all together | combine the steps in a real situation | two or three sentences use most of the steps | GSCS S4, p. 12; English S4, PDF p. 72 |

## Each language is practised in itself

A learner who chooses Kinyarwanda practises disagreeing politely **in Kinyarwanda**, not English explained in Kinyarwanda. The same goes for English, Kiswahili and French. The six steps stay the same, but the polite words, the respectful tone and the book pages come from that language:

| Language | Polite words the tutor looks for | Book pages |
|---|---|---|
| Kinyarwanda | Mbabarira, Ndumva, Wenda, Simbizi neza ariko…; “mwe” for a teacher or an elder | Ikinyarwanda S4, pp. 73–74 (ikiganiro mpaka) and GSCS S4, p. 12 |
| Kiswahili | Samahani, Nadhani, Labda, Tafadhali; Shikamoo for an elder | Kiswahili S4, pp. 20, 141, 149 (mjadala na mdahalo) and GSCS S4, p. 12 |
| French | Excuse-moi, Je pense que, Peut-être que; vouvoyer a teacher | Français S4, pp. 7, 23, 52 (respect mutuel, débat) and GSCS S4, p. 12 |
| English | could, would, I think, I’m not sure, please | as in the table above |

The GSCS page on active listening is in English. When a learner practises in another language, the tutor uses its ideas and explains them in that language.

## Speaking, not only writing

Fluency comes from speaking, so learners can answer with the microphone. For Kinyarwanda, speech is recognised by Digital Umuganda's Kinyarwanda Whisper model ([whisper_small_kinyarwanda](https://huggingface.co/DigitalUmuganda/whisper_small_kinyarwanda)); for the other languages, by Gemini. SOMA writes down exactly what they said, hesitations included and without correcting it, and shows how long they spoke and how many words per minute. The tutor then judges how the answer sounds when said aloud (fluency, hesitations, tone), not its spelling. Recordings are not stored.

## How the tutor teaches each step

- It gives an everyday situation (school, family, friends, sport) and asks the learner to try first. It never shows the answer before a try.
- After a try, it says what was good, then gives **one hint**: a question or a clue, not the corrected sentence.
- Only after two tries does it show an example, explain why it works, and ask the learner to try again in their own words.
- Feedback is green ("well done") or yellow ("not yet"). There are no red crosses.
- Everything happens in the chosen language: the situation, the learner's answer, the feedback and any example.

The sequence and the tutor's rules are in `src/soma/tutor.py`.

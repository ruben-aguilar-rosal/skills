---
name: optiak-writing
description: >
  How text reads at Optiak: Simplified Technical English, and what a pull request description
  must hold. Use when writing a pull request body, a commit message, a ticket, a review reply or
  a document, and when checking text somebody else wrote.
---

# optiak-writing

Rules for every English sentence an agent writes into a repository, a pull request or a ticket.

The behaviour reviewer reads this file and reports each breach. It reads only this file, so
write the rule out. Nothing here can be inferred.

Code and comments are `optiak-behaviours`. Where work goes is `optiak-tracker`.
Pull request limits and their reasons:
[Pull request hygiene](https://app.notion.com/p/Pull-request-hygiene-3c35b2a0c5b0816a9d25e97e08a145db).

---

## B6 — English that can be read two ways

**Rule.** Write every comment, document, commit message, pull request body and ticket in
Simplified Technical English: one meaning per word, active voice, simple tense, one idea per
sentence.

**Why.** Three readers parse this text and none of them can ask what you meant: a teammate who
does not speak English as a first language, an agent in a later session, and you in six months.
Ambiguous English does not fail loudly. Somebody reads it the wrong way once, acts on it, and
nobody traces the bug back to the sentence.

**The rules.**

| Rule | Do | Do not |
|---|---|---|
| One word, one meaning | Pick one verb per action and reuse it | Rotate `check`, `verify`, `confirm` for one action |
| One part of speech per word | "Apply oil to the valve" | "Oil the valve" |
| Active voice | "The loader parses the file" | "The file is parsed" |
| Simple tenses | "We received the report" | "We have received the report" |
| One idea per sentence | "Open the file. Read line 3." | "Open the file and read line 3, then check it" |
| Sentence length | 20 words for an instruction, 25 for a description | Long subordinate clauses |
| Noun clusters | Three words at most: "fuel pump valve" | "high pressure fuel pump inlet valve" |
| No ellipsis | Keep the subject, the verb and the article | Drop words to save space |
| Paragraphs | One topic, six sentences at most | Several topics in one block |
| Lists | A numbered list for three or more steps | A sequence buried in prose |
| Domain terms | Keep the term, define it once | Jargon that is never defined |

**Allowed.** Passive voice when the actor is genuinely unknown. A longer sentence when cutting it
would drop a safety condition, a scope qualifier or a number. Name the one you kept, and why.

**Not covered.** Code identifiers, test names and log format strings. Those follow the language.

**Check yourself.** Read each sentence once and ask whether a second reading is possible. If it
is, split the sentence.

**Related.** `unslop` (which cuts AI tells from the same text), `B4` (which decides how much to
write at all). `asd-ste100-skill` holds the full standard and rewrites a block of text on request.

---

## B5 — A pull request description nobody can review from

**Rule.** The description says what changed, where to look hardest, and what evidence
exists. Fill the repository's own template and add no sections to it. Everything else goes
where its reader already is: the ticket, `FOLLOW-UPS.md`, or a comment on the pull request.

**Why.** A reviewer rations attention, and the description is what they spend it on before
the diff. Bury the two sentences that needed challenging among forty that did not, and the
two do not get challenged — the description defeats itself. Length reads as thoroughness to
the person who wrote it and as noise to the person who has to act on it, and the reviewer is
the audience.

The body is also the wrong container for most of what lands in it. It is permanent, it is
read by everybody who touches the change later, and it cannot be collapsed. A review
transcript is for one developer, once. A follow-up's reasoning is for whoever picks the
ticket up, in the ticket. Put each where its reader will be.

**The limit is 150 words of prose**, counting nothing pasted. Human bodies in `iac-infra` run
240 to 1,300 characters and do not track diff size. Agent bodies in the same repository run
3,000 to 9,500. That gap is the behaviour.

**Do not write.**

- A section the template does not have. The template is three headings. A body with seven
  has four sections' worth of content in the wrong place.
- Review reports in the body. They are for the one developer approving the work. Post them
  as a comment, in full — moving them is about place, never about summarising them.
- A measurement you later retracted, followed by the retraction. Report the authoritative
  result only. *"Correction to that local run: the 6 in-place changes were an artefact of
  the dummy `-var` values"* is a note to yourself.
- What came back clean. *"Reported clean: quoting and word-splitting, `set -euo pipefail`
  interactions…"* asks the reviewer to read a list of non-events.
- The acceptance criteria walked through bullet by bullet when the description already says
  what was delivered. Name only the criteria that are **not** met.
- A follow-up's full reasoning and measurements when its ticket holds them. One line: what
  it is, and where it went.
- Rationale in a description bullet past the clause that stops a reviewer misreading the
  change.

**Write instead.** One bullet per change: what it does, and the one thing a reviewer would
otherwise get wrong about it. Anything deliberately not delivered, stated plainly and up
front. Evidence as the command and its result. Anything longer than that, as a comment.

**Allowed.**

- **Anything not delivered, at whatever length it takes to be unmissable.** A reviewer
  approving work that silently skipped an acceptance criterion is a worse failure than a
  long paragraph. This is the one place to spend words.
- Length in proportion to what the reviewer must **decide**, not to what you did. A change
  that turns on one subtle claim earns the space to state the claim.
- Test evidence in the body when it is short and it is the crux of the review.
- A long comment. The body is what this behaviour constrains; the pull request as a whole
  can hold as much as the work needs.

**Check yourself.** Count your sections against the template's. More than it has means the
extra belongs somewhere else. Then, for each paragraph: would a reviewer who has already
read the diff look at something different because of it? If not, cut it — or move it to the
ticket, the register, or a comment.

**Related.** `B4` (the same discipline for code and documentation), `B3` (which gives
follow-ups a home so the body does not have to be one), `ship-stack` (which fills the
template and writes the body).

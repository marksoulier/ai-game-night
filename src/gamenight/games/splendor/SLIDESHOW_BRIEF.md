# Build Brief: Splendor Game Night Kickoff Slideshow

**For the agent building this:** you're making a short slideshow to open game night --
the thing that plays on the TV/screen for 3-5 minutes while everyone settles in, right
before the Splendor tournament starts. This file is your brief: purpose, audience,
source-of-truth facts (already pulled accurately from this repo so you don't have to
re-derive or guess at them), a draft slide-by-slide outline with real copy, and the
guardrails to keep in mind. Treat the copy below as a strong first draft, not a rigid
script -- tighten wording, adjust pacing, restyle freely, but don't change the facts
without re-checking the source doc named next to them.

## Deliverable

A self-contained HTML slideshow, one slide per viewport, advanceable with arrow
keys/click (a simple `<section>`-per-slide + JS keydown handler is plenty -- no need for
a slide framework/library). Build it as an **Artifact** (load the `artifact-design`
skill first, per that tool's own instructions, to calibrate the visual treatment -- this
is an editorial/kickoff-energy deck, not a utilitarian doc, so that skill's "editorial"
path applies: make one real aesthetic choice and commit to it rather than defaulting to
a generic template look).

Target length: **10-12 slides**, each readable in 5-10 seconds at a glance from across
the room -- this plays while people are still finding seats, it is not read line by
line. Favor short, large text over paragraphs. No slide should need a full sentence read
aloud to land.

## Audience & Tone

Game night attendees -- a mix of people who already know Splendor and people who've
never played it, all there to watch (and maybe have played) AI bots compete. Tone is
**hype/kickoff energy, not a rules seminar or a technical readme** -- this is the "lights
dim, here's what we're about to watch" moment, not a tutorial. Assume nobody needs to
walk away able to *play* Splendor from this deck alone; they need to walk away excited
and oriented about what they're *watching*.

## Source-of-truth facts (don't invent numbers -- pull from here)

- Game rules, "one minute" summary, win condition: `README.md`'s "The Game In One
  Minute" section.
- Why Splendor was picked, "is it solved" research: `README.md`'s "Research" section
  (cites [atomicgametheory.com's "The Splendor Solution"](https://atomicgametheory.com/the-splendor-solution/)
  for the exploit-strategy finding -- quote/cite it, don't paraphrase into a stronger
  claim than "no proven solve exists").
- Player count / table seating / GUI layout: `README.md`'s "Player Count (2-4)" and "GUI
  Layout" sections.
- Reserved-card visibility rule (market-reserved cards are visible, blind reserves stay
  secret): `README.md`'s "Information Policy" section and `BOT_SPEC.md`'s
  "Reserved-Card Visibility" section.
- Tournament format (round robin -> seeded bracket -> live reveal): `README.md`'s
  "Tournament Mode & Bracket Reveal" section.
- Visual reference for what the live board actually looks like:
  `assets/gui_preview.svg` -- pull actual colors/shapes from this file for slide
  styling continuity (dark jeweler's-case palette, gem-colored tokens/pips), and feel
  free to embed a cropped/simplified version of it directly as a slide visual.

## Guardrails

- **Don't fabricate participant-specific stats.** It's tempting to make a "did you know"
  slide about bot performance (e.g. speed-check results), but any real number here comes
  from a specific person's submitted bot -- check with Mark before naming anyone or any
  bot by name, even in a lighthearted way. A generic version ("every bot's been
  speed-checked tonight so nothing stalls the room") is safe without checking; a specific
  one ("player X's bot took 900ms/action") is not.
- **Don't invent card data.** If you want a slide showing an example card, pull one from
  `EXAMPLES.md` (real engine output) rather than making up plausible-looking numbers --
  this repo already got burned once this project by asserting specific numbers from
  memory instead of checking, and the fix was "generate the data transparently and label
  it as such" -- don't undo that carefulness for a slide.
- **Keep rules explanation shallow.** Cover the shape of the game (collect gems, buy
  cards, race to 15 points), not edge cases (discard phase, noble-choice ties, blind
  reserve mechanics) -- those belong in `BOT_SPEC.md` for bot authors, not a kickoff
  slide for spectators.
- If you don't have the actual list of tonight's competing bots/players, leave a
  clearly-marked placeholder slide ("Tonight's Competitors: [fill in]") rather than
  inventing names.

## Draft Slide-By-Slide Outline

**1. Title**
"SPLENDOR" (large) / subtitle: "AI Game Night" / small: tonight's date. Visual: jewel
tones, maybe a few gem-token circles as decoration (reuse the palette from
`assets/gui_preview.svg`: white/blue/green/red/black/gold).

**2. The game, in one breath**
"Collect gem tokens. Buy cards that make future cards cheaper. First to 15 points wins."
Optional one more line: "2-4 players. Simple to learn, deep to master." (Source:
README's "Game In One Minute.")

**3. Why Splendor**
"No one has ever found a perfect strategy for this game." Sub-line: there's a known
*exploit* (hoard one gem color, skip cheap cards) that's strong but not proven optimal
-- so tonight's bots are playing a genuinely open contest, not a solved puzzle. (Source:
README's "Research" section -- keep the claim exactly this careful, don't upgrade
"no proven solve" to "provably impossible to solve.")

**4. Tonight, it's bots**
"Every player tonight is code." One line on the loop: each bot sees the board, picks one
of a list of legal moves, that's it. Optionally: "You can watch exactly what each bot
sees -- nothing is a black box." (This is the "AI Game Night" framing, not Splendor
specifically -- keep it short, it's scene-setting.)

**5. The table**
Show (or describe) the live board: everyone seated around a shared market, token bank,
and nobles in the middle -- built to look like a real table, not a spreadsheet. If
embedding a visual, crop from `assets/gui_preview.svg`.

**6. One rule twist worth knowing**
"If a card was taken from the open market, everyone saw it happen -- so you still get to
see it, even reserved." / "Cards reserved blind off the deck stay genuinely secret."
This is a nice, concrete, "huh, that's clever" beat for the room -- real information
design, not just flavor text. (Source: README's "Information Policy.")

**7. Tonight's format**
"Round robin first -- everyone plays everyone." Then: "Top finishers move into a
single-elimination bracket." Then: "We reveal it live, match by match." (Source:
README's "Tournament Mode & Bracket Reveal.")

**8. Tonight's competitors** *(placeholder -- fill in with actual entrant list/bot
names before presenting)*

**9. What to watch for**
2-3 bullets max, e.g.: "Who hoards gems vs. who builds fast." / "Whether anyone pulls
off the tier-1-skip exploit from slide 3." / "How close the final bracket match gets."

**10. Let's go**
"Round Robin begins now." Large, simple, energetic closing slide -- cue to start the
actual tournament run.

## Optional extra slides (only if time allows)

- A "how a bot decides" slide for the technically curious (one legal-action example,
  one chosen action, nothing more) -- skip this if the room skews non-technical.
- A last-call "still want to submit a bot next time?" slide pointing at this repo's
  Player Workflow (top-level `README.md`'s "Player Workflow" section, four directories
  up from this file at the repo root) -- only relevant if there's a recurring game night
  and people should know they can join next time.

## Reference files this brief pulled from

- `README.md` (this game's own, in `games/splendor/`)
- `BOT_SPEC.md`
- `EXAMPLES.md`
- `assets/gui_preview.svg`

<!-- Owner: yixiang0706 (card). Placeholder for the walking skeleton; not used yet. -->

TODO: system prompt for drafting the impact card.

Inputs the prompt will receive:
- PR title, description (author's reason) and diff
- `affected`: list of {module, owner, kind, files | symbol + location} from detect

Rules to keep (from the CP1 human-AI boundary):
- Explain and suggest only; never say a change is approved or rejected.
- Do not invent a reason the author did not give.
- Label anything inferred as a possible impact, not a fact.

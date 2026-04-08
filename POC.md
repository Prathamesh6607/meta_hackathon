# Email Triage OpenEnv POC

## What to show

A short demo that proves the system can:
1. accept an incoming support message,
2. classify or route it,
3. retrieve similar cases from the Meta-focused corpus,
4. produce a readable recommendation for the next action,
5. show stats that prove the index is real and populated.

## Demo flow

### 1. Open the UI
Go to:

```text
http://127.0.0.1:8000/ui
```

### 2. Show the corpus stats
Point at the top of the search panel and call out:
- record count
- unique token count
- top labels

This is your proof that the assistant is grounded in a real indexed corpus.

### 3. Show the corpus-backed search
In the Support Search box, try:

```text
Meta login privacy account issue
```

Explain that the app returns ranked matches with snippets, scores, and metadata.

### 4. Show the POC task flow
Pick `task_1`, then click `Auto Next` or `Run Episode`.

Explain:
- the app classifies the message,
- the backend grades the action,
- the UI shows the final response,
- the support recommendation panel explains the result,
- the same corpus can be used to ground future support responses.

### 4.1 Show self-learning proof (expected output)
In the Self-Learning Module, call out these fields and what they mean:
- Examples Seen and Updates should increase as you run steps.
- Epoch Run should increase each time a new episode starts.
- Log Entries should increase as learning events are recorded.
- Recommended Model can show `TF-IDF + Logistic Regression`.
- Model In Use can show `Online linear policy with heuristic features`.
- Using Recommended can show `No` when the active model differs from the recommended baseline.
- Policy File should show `task1_agent_policy.json`, proving persistence across runs.
- Category Bias and Priority Bias values should be non-zero after a few learning updates.

Use this line in your talk track:
"The learner is active and updating online. You can see examples, updates, epoch count, and persisted policy state changing live in the UI."

### 5. Show why it is useful for Meta
Talk track:
- it is explainable, not just a black-box reply,
- it uses an inverted index for fast lookup,
- it uses a Meta-focused subset for support triage,
- it can be adapted to Meta support categories like Facebook, Instagram, WhatsApp, and Messenger,
- it is suitable as a triage assistant or support routing prototype.

## One-minute pitch

"This prototype takes incoming support messages, matches them against a Meta-focused support corpus, and produces a ranked recommendation with an explanation. It is built for fast customer-support triage, with a live UI, corpus stats, and a retrieval-backed workflow that can be adapted to Meta channels like Facebook, Instagram, WhatsApp, and Messenger."

## What makes it a POC

- Browser UI
- Support search
- Corpus-backed retrieval
- Meta-themed visual design
- Task execution flow
- Human-readable outcome summary
- Corpus stats card
- Meta subset file already generated

## Best screenshot to capture

Take a screenshot of the UI with:
- the Support Search results visible,
- the corpus stats card visible,
- the final task response panel visible.

That screenshot tells the story in one frame.

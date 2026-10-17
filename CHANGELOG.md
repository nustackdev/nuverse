# Changelog

The full commit stream, every package. Newest first.

- Add a Chat plane: the agent answers by drawing cells, woken by a reaction
- Say a Log plane's Config applies to that plane only
- Move nulog into nuverse, its viewer rewritten as Log planes, one per store
- Release nuagent 0.2.1 on nuskills 0.2.0, chaining-first prompts
- Tell the agent its world is already provided, no wrapping needed
- Release nuagent 0.2.0, the Nu agent loop, on nu 0.6.4
- Rename nuverse-demos to nudemos
- Add nuagent kv store: durable runs on one sqlite file, no lock held across model calls
- Build nuagent's opening prompt from nuskills, the live catalogue and the caller's world
- Add nuagent backends: Claude Code sessions and any OpenAI-compatible model
- Add the nuagent loop: the model answers in Nu, the space runs it
- Add nuagent, an empty package for the Nu agent loop
- Rewrite the README for users: logo header, what it is, how to install
- The Program snippet is gone: nuspace's Empty cell is the plain program now
- Add nuverse-demos: the counter, sampled and movies demos as nuspace Planes
- nuverse moves out of nuspace into its own monorepo of extensions
- Add nuverse-log, a placeholder Log plane
- Park the Claude Code chat plane with the nuspace agent

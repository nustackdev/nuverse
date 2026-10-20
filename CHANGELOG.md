# Changelog

The full commit stream, every package. Newest first.

- Add the Design demo: the nustack design system as one live spec
- Release nuverse 0.3.3, nulog 0.2.1, nuagent 0.2.2, nudemos 0.1.1 on nu 0.6.5
- Show transactions read in the memes Monitor, every one in every block
- Drop the Plain plane: nuspace now has its own empty plane built in
- Shorten plane names now that each carries its package: chat, log, tour
- Record what nuagent and the Jobs plane make under their package-qualified names
- Ship nuverse with nuspace: the host installs it, nuverse no longer pulls nuspace in
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

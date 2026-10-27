# Agent settings

Agent detail uses the shared compact model/reasoning menu backed by the model catalog. Its Custom dialog contains provider and model columns; choosing a different provider clears only the dialog draft. Cancel discards that draft. Model presets and reasoning effort are saved with Agent settings. Previously saved unavailable values remain visible, and the main Save action requires an available provider/model pair. Agents without owner permissions show disabled selectors.

The main Save action snapshots the model, settings, and workflow/template selections. Repeated saves and simultaneous metadata saves are blocked. A failed request retains the draft and the last saved baseline. A successful response updates that baseline; edits made while the request was pending remain in the draft. Navigation to chat is disabled while either save is pending.

The metadata dialog validates its own form and saves only avatar, name, and description. Successful metadata saves synchronize those fields and the returned version/time without replacing unsaved model, prompt, or workflow selections. Failed validation or requests leave the dialog open. Each opening starts from current agent metadata.

Loading another agent or leaving the component invalidates pending load/save responses. Failed loads offer Retry. Unsaved changes retain the leave confirmation, including explicit cancellation of navigation.

Backend updates preserve workflow/template relations when their fields are omitted, replace an explicitly provided UUID list, and clear an explicit empty list. Invalid lists return 400. Relation changes and agent field persistence share a database transaction. New conversations inherit saved model, provider, settings, and relations; explicit conversation configuration overrides remain supported.

## Verification

Backend tests use temporary SQLite databases without external services. Frontend tests mount compiled Vue components and exercise selectors, save failures, pending edits, metadata validation, and stale responses.

# Model selection

Model controls share `ModelSelector.vue`, which searches the supplied flat options and leaves the selected value unchanged until the user selects or clears it.

Workflow model fields retain their stored values when mounted, restored, or refreshed from the settings catalog. A missing model is shown as unavailable only after a successful catalog load. Empty model fields stay empty; the catalog does not select its first entry. Existing provider-specific template defaults remain defaults for new nodes. Universal and custom model templates start with an empty model.

Universal LLM provider choices and custom/local model family choices are searchable. A user changing the provider or family clears its model field so the user can choose from the new list. Restoring a provider or family through workflow history does not clear its model. Missing providers and families remain visible with an unavailable hint.

Model catalog options are computed from current settings, including enabled models and multimodal eligibility. The hydration helpers update options without replacing field values. Provider, family, and model fields retain their `BaseField` wrappers and connection handles.

Chat model changes use a draft. Changing its provider clears the draft model; canceling restores the conversation's existing selection. Confirmation requires an available provider/model pair. A saved conversation updates its displayed selection only after the save succeeds; a failed save retains the draft for retry. Replies from an earlier conversation or an unmounted selector do not update the current conversation. New conversations use the draft locally until created.

Search matches model names and IDs without case sensitivity. Explicitly disabled local models are excluded from both chat and workflow family choices; family models without local backend metadata remain selectable. Automated coverage is in `frontend/tests/modelSelection.test.js`.

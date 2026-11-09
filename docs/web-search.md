# Web search and embedding settings

Network search settings expose Jina and DeepSeek. The retired Bing configuration is removed when saved settings load or update. Text Search nodes offer `jina.ai` and `deepseek`; Image Search offers Pexels. Opening an old node refreshes its engine choices and clears unsupported selections. Executing a saved unsupported engine fails with an actionable input error before making a network request; it does not silently switch providers.

## DeepSeek

Configure the full Search endpoint and API key in Settings → Network search → DeepSeek. The default is `https://api.deepseek.com/v1/tools/search`. Search uses an explicit bearer key and a JSON POST request with `query`, `count` and `need_content: false`. Queries contain 1–128 Unicode characters and request 1–50 results. Returned titles, URLs and snippets feed the existing workflow output fields; a missing short snippet falls back to the summary. Batch input, separate result lists, combined output, Markdown/text formatting and snippet length remain supported. Clients close after execution. Search errors, invalid credentials, insufficient balance and rate limits fail explicitly without echoing provider error bodies or retrying unchanged requests automatically.

This uses the standalone Search API and does not make a model completion or Fetch request. Authentication is independent of the model endpoint editor: enter the DeepSeek API key in network search settings. Requests use the application's configured HTTP networking policy.

References: [Search API schema](https://api-docs.deepseek.com/zh-cn/api/search/) and [Search & Fetch guide](https://api-docs.deepseek.com/zh-cn/guides/search/).

## Embedding configuration

All seven embedding provider tabs render the default endpoint selector and model editor, including when a saved configuration omits a provider. Empty tabs explain how to add a model and bind an endpoint; shared endpoint URLs and keys are managed in LLM endpoints. Runtime settings fill missing embedding provider defaults after applying an external LLM settings file, without rewriting that file merely to read it.

Editing an endpoint binding replaces that binding. Duplicate model keys cannot overwrite another saved model, and unedited extra model properties survive changes. Model and search settings use the single page-level Save settings action. External LLM configuration changes persist to that file, while network search settings persist in application settings.

Validation covers provider initialization, embedding model/binding edits, settings reloads, search request schema and validation, empty/malformed results, error handling, workflow output shapes, retired engine rejection and Jina count/key handling. A script-based live DeepSeek Text Search workflow verified nonempty title, URL and snippet output using the authorized key without returning it.

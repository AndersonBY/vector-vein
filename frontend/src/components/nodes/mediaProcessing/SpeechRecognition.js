/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 12:14:23
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-07-10 17:54:49
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "media_processing.speech_recognition",
    "has_inputs": true,
    "template": {
      "engine": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "openai",
        "options": [
          {
            "value": "openai",
            "label": "OpenAI"
          },
          {
            "value": "deepgram",
            "label": "Deepgram"
          },
        ],
        "name": "engine",
        "display_name": "engine",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "files_or_urls": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "files",
        "options": [
          {
            "value": "files",
            "label": "files"
          },
          {
            "value": "urls",
            "label": "urls"
          },
        ],
        "name": "files_or_urls",
        "display_name": "files_or_urls",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "radio"
      },
      "files": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": [],
        "name": "files",
        "display_name": "files",
        "type": "str",
        "list": false,
        "field_type": "file",
        "support_file_types": ".wav, .mp3, .mp4, .m4a, .wma, .aac, .ogg, .amr, .flac",
        "condition": (fieldsData) => {
          return fieldsData.files_or_urls.value == 'files'
        }
      },
      "urls": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "urls",
        "display_name": "urls",
        "type": "str",
        "list": false,
        "field_type": "input",
        "condition": (fieldsData) => {
          return fieldsData.files_or_urls.value == 'urls'
        }
      },
      "output_type": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "text",
        "options": [
          {
            "value": "text",
            "label": "text"
          },
          {
            "value": "list",
            "label": "list"
          },
          {
            "value": "srt",
            "label": "srt"
          },
        ],
        "name": "output_type",
        "display_name": "output_type",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output",
        "display_name": "output",
        "type": "str",
        "list": false,
        "field_type": "",
        "is_output": true
      },
    }
  }
}
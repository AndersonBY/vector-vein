/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 02:35:32
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-24 16:12:13
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "output.audio",
    "has_inputs": true,
    "template": {
      "audio_type": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "text_to_speech",
        "options": [
          {
            "value": "text_to_speech",
            "label": "text_to_speech"
          },
          {
            "value": "play_audio",
            "label": "play_audio"
          },
        ],
        "name": "audio_type",
        "display_name": "audio_type",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "file_link": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "file_link",
        "display_name": "file_link",
        "type": "str",
        "list": false,
        "field_type": "textarea",
        "condition": (fieldsData) => {
          return fieldsData.audio_type.value == 'play_audio'
        }
      },
      "content": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "content",
        "display_name": "content",
        "type": "str",
        "list": false,
        "field_type": "textarea",
        "condition": (fieldsData) => {
          return fieldsData.audio_type.value == 'text_to_speech'
        },
      },
      "direct_play": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": false,
        "name": "direct_play",
        "display_name": "direct_play",
        "type": "bool",
        "clear_after_run": false,
        "list": false,
        "field_type": "checkbox",
      },
      "tts_provider": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "openai",
        "options": [
          {
            "value": "openai",
            "label": "openai"
          },
          {
            "value": "minimax",
            "label": "minimax"
          },
          {
            "value": "piper",
            "label": "piper"
          },
        ],
        "name": "tts_provider",
        "display_name": "tts_provider",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select",
        "condition": (fieldsData) => {
          return fieldsData.audio_type.value == 'text_to_speech'
        },
        "group": "default",
      },
      "tts_model": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "tts-1",
        "options": [
          {
            "value": "tts-1",
            "label": "OpenAI tts-1"
          },
          {
            "value": "tts-1-hd",
            "label": "OpenAI tts-1-hd"
          },
          {
            "value": "speech-01",
            "label": "Minimax speech-01"
          },
        ],
        "name": "tts_model",
        "display_name": "tts_model",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select",
        "condition": (fieldsData) => {
          return fieldsData.audio_type.value == 'text_to_speech'
        },
        "group": "default",
      },
      "tts_voice": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "onyx",
        "options": [
          {
            "value": "alloy",
            "label": "OpenAI alloy",
          },
          {
            "value": "echo",
            "label": "OpenAI echo",
          },
          {
            "value": "fable",
            "label": "OpenAI fable",
          },
          {
            "value": "onyx",
            "label": "OpenAI onyx",
          },
          {
            "value": "nova",
            "label": "OpenAI nova",
          },
          {
            "value": "shimmer",
            "label": "OpenAI shimmer",
          },
          {
            "value": "male-qn-qingse",
            "label": "Minimax male-qn-qingse",
          },
          {
            "value": "male-qn-jingying",
            "label": "Minimax male-qn-jingying",
          },
          {
            "value": "male-qn-badao",
            "label": "Minimax male-qn-badao",
          },
          {
            "value": "male-qn-daxuesheng",
            "label": "Minimax male-qn-daxuesheng",
          },
          {
            "value": "female-shaonv",
            "label": "Minimax female-shaonv",
          },
          {
            "value": "female-yujie",
            "label": "Minimax female-yujie",
          },
          {
            "value": "female-chengshu",
            "label": "Minimax female-chengshu",
          },
          {
            "value": "female-tianmei",
            "label": "Minimax female-tianmei",
          },
          {
            "value": "presenter_male",
            "label": "Minimax presenter_male",
          },
          {
            "value": "presenter_female",
            "label": "Minimax presenter_female",
          },
          {
            "value": "audiobook_male_1",
            "label": "Minimax audiobook_male_1",
          },
          {
            "value": "audiobook_male_2",
            "label": "Minimax audiobook_male_2",
          },
          {
            "value": "audiobook_female_1",
            "label": "Minimax audiobook_female_1",
          },
          {
            "value": "audiobook_female_2",
            "label": "Minimax audiobook_female_2",
          },
          {
            "value": "male-qn-qingse-jingpin",
            "label": "Minimax male-qn-qingse-jingpin",
          },
          {
            "value": "male-qn-jingying-jingpin",
            "label": "Minimax male-qn-jingying-jingpin",
          },
          {
            "value": "male-qn-badao-jingpin",
            "label": "Minimax male-qn-badao-jingpin",
          },
          {
            "value": "male-qn-daxuesheng-jingpin",
            "label": "Minimax male-qn-daxuesheng-jingpin",
          },
          {
            "value": "female-shaonv-jingpin",
            "label": "Minimax female-shaonv-jingpin",
          },
          {
            "value": "female-yujie-jingpin",
            "label": "Minimax female-yujie-jingpin",
          },
          {
            "value": "female-chengshu-jingpin",
            "label": "Minimax female-chengshu-jingpin",
          },
          {
            "value": "female-tianmei-jingpin",
            "label": "Minimax female-tianmei-jingpin",
          },
        ],
        "name": "tts_voice",
        "display_name": "tts_voice",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select",
        "condition": (fieldsData) => {
          return fieldsData.audio_type.value == 'text_to_speech'
        },
        "group": "default",
      },
      "output_type": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "markdown",
        "options": [
          {
            "value": "only_link",
            "label": "only_link"
          },
          {
            "value": "markdown",
            "label": "markdown"
          },
          {
            "value": "html",
            "label": "html"
          },
        ],
        "name": "output_type",
        "display_name": "output_type",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "show_player": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": true,
        "name": "show_player",
        "display_name": "show_player",
        "type": "bool",
        "clear_after_run": false,
        "list": false,
        "field_type": "checkbox"
      },
      "output": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output",
        "display_name": "output",
        "type": "str",
        "clear_after_run": false,
        "list": false,
        "field_type": "input",
        "is_output": true
      },
    }
  }
}
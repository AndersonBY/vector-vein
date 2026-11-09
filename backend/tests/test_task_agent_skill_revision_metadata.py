"""Historical inspection uses native parsed metadata from the retained revision."""
from task_agent.skills import SkillsLibrary


def test_retained_files_metadata_uses_original_native_yaml_after_catalog_changes(tmp_path):
    library = SkillsLibrary(tmp_path / "task-agent")
    original = library.save({
        "skill_id": "metadata_skill",
        "content": "---\nname: 'revision-helper' # original name\n"
                   "description: |\n  First description line.\n  Second description line.\n"
                   "---\nOriginal instructions.\n",
    })
    library.save({
        "skill_id": "metadata_skill",
        "content": "---\nname: changed-helper\ndescription: New description.\n---\nNew instructions.\n",
    })
    library.delete("metadata_skill")

    retained = library.files("metadata_skill", version=1)
    assert retained["version"] == 1
    assert retained["name"] == original["name"] == "revision-helper"
    assert retained["description"] == original["description"]
    assert "Second description line." in retained["description"]
    assert "bundle_path" not in retained and "content" not in retained

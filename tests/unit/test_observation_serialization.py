from openhands.core.schema.observation import ObservationType
from openhands.events.action.files import FileEditSource
from openhands.events.observation import (
    CmdOutputMetadata,
    CmdOutputObservation,
    FileEditObservation,
    Observation,
    RecallObservation,
    RecallType,
)
from openhands.events.serialization import (
    event_from_dict,
    event_to_dict,
    event_to_memory,
    event_to_trajectory,
)
from openhands.events.serialization.observation import observation_from_dict


def serialization_deserialization(
    original_observation_dict, cls, max_message_chars: int = 10000
):
    observation_instance = event_from_dict(original_observation_dict)
    assert isinstance(
        observation_instance, Observation
    ), 'The observation instance should be an instance of Action.'
    assert isinstance(
        observation_instance, cls
    ), 'The observation instance should be an instance of CmdOutputObservation.'
    serialized_observation_dict = event_to_dict(observation_instance)
    serialized_observation_trajectory = event_to_trajectory(observation_instance)
    serialized_observation_memory = event_to_memory(
        observation_instance, max_message_chars
    )
    assert (
        serialized_observation_dict == original_observation_dict
    ), 'The serialized observation should match the original observation dict.'
    assert (
        serialized_observation_trajectory == original_observation_dict
    ), 'The serialized observation trajectory should match the original observation dict.'
    original_observation_dict.pop('message', None)
    original_observation_dict.pop('id', None)
    original_observation_dict.pop('timestamp', None)
    assert (
        serialized_observation_memory == original_observation_dict
    ), 'The serialized observation memory should match the original observation dict.'


# Additional tests for various observation subclasses can be included here
def test_observation_event_props_serialization_deserialization():
    original_observation_dict = {
        'id': 42,
        'source': 'agent',
        'timestamp': '2021-08-01T12:00:00',
        'observation': 'run',
        'message': 'Command `ls -l` executed with exit code 0.',
        'extras': {
            'command': 'ls -l',
            'hidden': False,
            'metadata': {
                'exit_code': 0,
                'hostname': None,
                'pid': -1,
                'prefix': '',
                'py_interpreter_path': None,
                'suffix': '',
                'username': None,
                'working_dir': None,
            },
        },
        'content': 'foo.txt',
        'success': True,
    }
    serialization_deserialization(original_observation_dict, CmdOutputObservation)


def test_command_output_observation_serialization_deserialization():
    original_observation_dict = {
        'observation': 'run',
        'extras': {
            'command': 'ls -l',
            'hidden': False,
            'metadata': {
                'exit_code': 0,
                'hostname': None,
                'pid': -1,
                'prefix': '',
                'py_interpreter_path': None,
                'suffix': '',
                'username': None,
                'working_dir': None,
            },
        },
        'message': 'Command `ls -l` executed with exit code 0.',
        'content': 'foo.txt',
        'success': True,
    }
    serialization_deserialization(original_observation_dict, CmdOutputObservation)


def test_success_field_serialization():
    # Test success=True
    obs = CmdOutputObservation(
        content='Command succeeded',
        command='ls -l',
        metadata=CmdOutputMetadata(
            exit_code=0,
        ),
    )
    serialized = event_to_dict(obs)
    assert serialized['success'] is True

    # Test success=False
    obs = CmdOutputObservation(
        content='No such file or directory',
        command='ls -l',
        metadata=CmdOutputMetadata(
            exit_code=1,
        ),
    )
    serialized = event_to_dict(obs)
    assert serialized['success'] is False


def test_legacy_serialization():
    original_observation_dict = {
        'id': 42,
        'source': 'agent',
        'timestamp': '2021-08-01T12:00:00',
        'observation': 'run',
        'message': 'Command `ls -l` executed with exit code 0.',
        'extras': {
            'command': 'ls -l',
            'hidden': False,
            'exit_code': 0,
            'command_id': 3,
        },
        'content': 'foo.txt',
        'success': True,
    }
    event = event_from_dict(original_observation_dict)
    assert isinstance(event, Observation)
    assert isinstance(event, CmdOutputObservation)
    assert event.metadata.exit_code == 0
    assert event.success is True
    assert event.command == 'ls -l'
    assert event.hidden is False

    event_dict = event_to_dict(event)
    assert event_dict['success'] is True
    assert event_dict['extras']['metadata']['exit_code'] == 0
    assert event_dict['extras']['metadata']['pid'] == 3
    assert event_dict['extras']['command'] == 'ls -l'
    assert event_dict['extras']['hidden'] is False


def test_file_edit_observation_serialization():
    original_observation_dict = {
        'observation': 'edit',
        'extras': {
            '_diff_cache': None,
            'impl_source': FileEditSource.LLM_BASED_EDIT,
            'new_content': None,
            'old_content': None,
            'path': '',
            'prev_exist': False,
            'diff': None,
        },
        'message': 'I edited the file .',
        'content': '[Existing file /path/to/file.txt is edited with 1 changes.]',
    }
    serialization_deserialization(original_observation_dict, FileEditObservation)


def test_file_edit_observation_new_file_serialization():
    original_observation_dict = {
        'observation': 'edit',
        'content': '[New file /path/to/newfile.txt is created with the provided content.]',
        'extras': {
            '_diff_cache': None,
            'impl_source': FileEditSource.LLM_BASED_EDIT,
            'new_content': None,
            'old_content': None,
            'path': '',
            'prev_exist': False,
            'diff': None,
        },
        'message': 'I edited the file .',
    }

    serialization_deserialization(original_observation_dict, FileEditObservation)


def test_file_edit_observation_oh_aci_serialization():
    original_observation_dict = {
        'observation': 'edit',
        'content': 'The file /path/to/file.txt is edited with the provided content.',
        'extras': {
            '_diff_cache': None,
            'impl_source': FileEditSource.LLM_BASED_EDIT,
            'new_content': None,
            'old_content': None,
            'path': '',
            'prev_exist': False,
            'diff': None,
        },
        'message': 'I edited the file .',
    }
    serialization_deserialization(original_observation_dict, FileEditObservation)


def test_file_edit_observation_legacy_serialization():
    original_observation_dict = {
        'observation': 'edit',
        'content': 'content',
        'extras': {
            'path': '/workspace/game_2048.py',
            'prev_exist': False,
            'old_content': None,
            'new_content': 'new content',
            'impl_source': 'oh_aci',
            'formatted_output_and_error': 'File created successfully at: /workspace/game_2048.py',
        },
    }

    event = event_from_dict(original_observation_dict)
    assert isinstance(event, Observation)
    assert isinstance(event, FileEditObservation)
    assert event.impl_source == FileEditSource.OH_ACI
    assert event.path == '/workspace/game_2048.py'
    assert event.prev_exist is False
    assert event.old_content is None
    assert event.new_content == 'new content'
    assert not hasattr(event, 'formatted_output_and_error')

    event_dict = event_to_dict(event)
    assert event_dict['extras']['impl_source'] == 'oh_aci'
    assert event_dict['extras']['path'] == '/workspace/game_2048.py'
    assert event_dict['extras']['prev_exist'] is False
    assert event_dict['extras']['old_content'] is None
    assert event_dict['extras']['new_content'] == 'new content'
    assert 'formatted_output_and_error' not in event_dict['extras']


def test_recall_observation_serialization():
    original_observation_dict = {
        'observation': 'recall',
        'extras': {
            'recall_type': RecallType.ENVIRONMENT_INFO,
            'repo_name': 'some_repo_name',
            'repo_directory': 'some_repo_directory',
            'runtime_hosts': ['host1', 'host2'],
            'repo_instructions': 'complex_repo_instructions',
        },
    }
    serialization_deserialization(original_observation_dict, RecallObservation)


def test_recall_observation_microagent_knowledge_serialization():
    original_observation_dict = {
        'observation': 'recall',
        'extras': {
            'recall_type': RecallType.MICROAGENT_KNOWLEDGE,
            'microagent_knowledge': [
                {
                    'agent_name': 'microagent1',
                    'trigger_word': 'trigger_word1',
                    'content': 'content1',
                },
                {
                    'agent_name': 'microagent2',
                    'trigger_word': 'trigger_word2',
                    'content': 'content2',
                },
            ],
        },
    }
    serialization_deserialization(original_observation_dict, RecallObservation)


def test_recall_observation_knowledge_microagent_serialization():
    """Test serialization of a RecallObservation with KNOWLEDGE_MICROAGENT type."""
    # Create a RecallObservation with triggered microagent content
    original = RecallObservation(
        content='Knowledge microagent information',
        recall_type=RecallType.KNOWLEDGE_MICROAGENT,
        triggered_content=[
            {
                'agent_name': 'python_best_practices',
                'trigger_word': 'python',
                'content': 'Always use virtual environments for Python projects.',
            },
            {
                'agent_name': 'git_workflow',
                'trigger_word': 'git',
                'content': 'Create a new branch for each feature or bugfix.',
            },
        ],
    )

    # Serialize to dictionary
    serialized = event_to_dict(original)

    # Verify serialized data structure
    assert serialized['observation'] == ObservationType.RECALL
    assert serialized['content'] == 'Knowledge microagent information'
    assert serialized['extras']['recall_type'] == RecallType.KNOWLEDGE_MICROAGENT.value
    assert len(serialized['extras']['triggered_content']) == 2
    assert serialized['extras']['triggered_content'][0]['trigger_word'] == 'python'

    # Deserialize back to RecallObservation
    deserialized = observation_from_dict(serialized)

    # Verify properties are preserved
    assert deserialized.recall_type == RecallType.KNOWLEDGE_MICROAGENT
    assert deserialized.triggered_content == original.triggered_content
    assert deserialized.content == original.content

    # Check that environment info fields are None
    assert deserialized.repository_name is None
    assert deserialized.repository_directory is None
    assert deserialized.repository_instructions is None
    assert deserialized.runtime_hosts is None


def test_recall_observation_environment_info_serialization():
    """Test serialization of a RecallObservation with ENVIRONMENT_INFO type."""
    # Create a RecallObservation with environment info
    original = RecallObservation(
        content='Environment information',
        recall_type=RecallType.ENVIRONMENT_INFO,
        repository_name='OpenHands',
        repository_directory='/workspace/openhands',
        repository_instructions="Follow the project's coding style guide.",
        runtime_hosts={'127.0.0.1': 8080, 'localhost': 5000},
    )

    # Serialize to dictionary
    serialized = event_to_dict(original)

    # Verify serialized data structure
    assert serialized['observation'] == ObservationType.RECALL
    assert serialized['content'] == 'Environment information'
    assert serialized['extras']['recall_type'] == RecallType.ENVIRONMENT_INFO.value
    assert serialized['extras']['repository_name'] == 'OpenHands'
    assert serialized['extras']['runtime_hosts'] == {
        '127.0.0.1': 8080,
        'localhost': 5000,
    }

    # Deserialize back to RecallObservation
    deserialized = observation_from_dict(serialized)

    # Verify properties are preserved
    assert deserialized.recall_type == RecallType.ENVIRONMENT_INFO
    assert deserialized.repository_name == original.repository_name
    assert deserialized.repository_directory == original.repository_directory
    assert deserialized.repository_instructions == original.repository_instructions
    assert deserialized.runtime_hosts == original.runtime_hosts

    # Check that knowledge microagent fields are None
    assert deserialized.triggered_content is None


def test_recall_observation_combined_serialization():
    """Test serialization of a RecallObservation with both types of information."""
    # Create a RecallObservation with both environment and microagent info
    # Note: In practice, recall_type would still be one specific type,
    # but the object could contain both types of fields
    original = RecallObservation(
        content='Combined information',
        recall_type=RecallType.ENVIRONMENT_INFO,
        # Environment info
        repository_name='OpenHands',
        repository_directory='/workspace/openhands',
        repository_instructions="Follow the project's coding style guide.",
        runtime_hosts={'127.0.0.1': 8080},
        # Knowledge microagent info
        triggered_content=[
            {
                'agent_name': 'python_best_practices',
                'trigger_word': 'python',
                'content': 'Always use virtual environments for Python projects.',
            }
        ],
    )

    # Serialize to dictionary
    serialized = event_to_dict(original)

    # Verify serialized data has both types of fields
    assert serialized['extras']['recall_type'] == RecallType.ENVIRONMENT_INFO.value
    assert serialized['extras']['repository_name'] == 'OpenHands'
    assert (
        serialized['extras']['triggered_content'][0]['agent_name']
        == 'python_best_practices'
    )

    # Deserialize back to RecallObservation
    deserialized = observation_from_dict(serialized)

    # Verify all properties are preserved
    assert deserialized.recall_type == RecallType.ENVIRONMENT_INFO

    # Environment properties
    assert deserialized.repository_name == original.repository_name
    assert deserialized.repository_directory == original.repository_directory
    assert deserialized.repository_instructions == original.repository_instructions
    assert deserialized.runtime_hosts == original.runtime_hosts

    # Knowledge microagent properties
    assert deserialized.triggered_content == original.triggered_content

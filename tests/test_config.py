from pathlib import Path

import pytest
import yaml

from pycnysr.pycnysr import RepoConfig


@pytest.fixture
def config_files() -> list[Path]:
    return list(Path(__file__).parents[1].glob('config*.yaml'))


def test_at_least_one_config(config_files: list[Path]) -> None:

    assert len(list(config_files)) >= 1


def test_structures(config_files: list[Path]) -> None:

    for config_file in config_files:
        configurations = yaml.safe_load(config_file.read_bytes())

        for repo_name, repo_configuration in configurations.items():

            assert isinstance(
                RepoConfig(**repo_configuration, name=repo_name), RepoConfig
            )

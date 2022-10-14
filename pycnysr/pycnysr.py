import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Thread
from time import sleep

import click
import yaml
from loguru import logger
from notifypy import Notify
from pydantic import BaseModel, validator
from watchdog.events import FileSystemEvent, RegexMatchingEventHandler
from watchdog.observers import Observer
from watchdog.utils.bricks import SkipRepeatsQueue

BASH_BINARY: str = 'bash'
RSYNC_BINARY: str = 'rsync'


class EventHandlerConfig(BaseModel):
    """regex event handler configuration."""

    # nothing is excluded
    excludes: list[str] = []

    # everything is included
    includes: list[str] = ['.*']


class RsyncConfig(BaseModel):
    """rsync configuration."""

    # filters expressed as they should be used with rsync. see section
    # "FILTER RULES" of the rsync manual page
    filters: list[str] = []

    # rsync options
    options: list[str] = ['--archive', '--delete', '-e ssh']


class RepoConfig(BaseModel):
    """a model for a repository configuration."""

    event_handler: EventHandlerConfig = EventHandlerConfig()
    name: str
    notify: bool = False
    rsync: RsyncConfig = RsyncConfig()
    source: str
    destinations: list[str]

    class Config:
        extra = 'forbid'

    @validator('source')
    def expand_tilde(cls, v: str) -> str:
        """expand source path"""
        return os.path.expanduser(v)


class QueueItem(BaseModel):

    configuration: RepoConfig
    event: FileSystemEvent

    class Config:
        extra = 'forbid'
        arbitrary_types_allowed = True


class EventHandler(RegexMatchingEventHandler):
    """a custom handler."""

    def __init__(
        self, configuration: RepoConfig, queue: SkipRepeatsQueue
    ) -> None:
        super().__init__(
            regexes=configuration.event_handler.includes,
            ignore_regexes=configuration.event_handler.excludes,
            ignore_directories=True,
        )

        self.configuration = configuration
        self.queue = queue

    def on_any_event(self, event: FileSystemEvent) -> None:
        """handle all kinds of events."""

        self.queue.put(QueueItem(configuration=self.configuration, event=event))


def process_queue(queue: SkipRepeatsQueue) -> None:
    while True:
        if not queue.empty():
            queue_item = queue.get()
            event = queue_item.event
            configuration = queue_item.configuration

            logger.info(f'synchronizing {event.src_path}')

            # generate a temp file
            with NamedTemporaryFile() as tmp:

                tempfile = Path(tmp.name)

                # in which we dump the rsync filter rules
                tempfile.write_text('\n'.join(configuration.rsync.filters))

                # for each destination
                for to_directory in configuration.destinations:

                    # generate the command line
                    command_line = ' '.join(
                        [
                            shutil.which(RSYNC_BINARY),  # type: ignore[list-item] # noqa: E501
                            *configuration.rsync.options,
                            f"--filter='merge {tempfile}'",
                            configuration.source,
                            to_directory,
                        ]
                    )

                    logger.debug(f'executed command is {command_line}')

                    # execute it
                    process = subprocess.Popen(
                        command_line,
                        shell=True,
                        executable=shutil.which(BASH_BINARY),
                    )
                    _, stderr = process.communicate()

                    # eventually notify
                    if configuration.notify:
                        notification = Notify()
                        notification.title = 'PyCNYSR'

                        if process.returncode == 0:
                            notification.message = (
                                f'{configuration.name} synchronized'
                            )
                        else:
                            notification.message = '{} synchronization failed with error {}'.format(  # noqa: E501
                                configuration.name, str(stderr)
                            )

                        notification.send()


@click.command()
@click.option(
    '--config',
    default=str(Path(Path.home()).joinpath('config.yaml')),
    help='configuration file',
)
@click.option(
    '--log',
    default='info',
    type=click.Choice(['info', 'debug', 'warning'], case_sensitive=False),
    help='log level',
)
def main(config: str, log: str) -> None:
    """a simple multi directory watcher and syncer"""

    # log level
    log_level = log.upper()
    logger.remove()
    logger.add(
        sys.stdout,
        format='<green>{time:YYYY-MM-DD HH:mm:ss}</green> <level>{level}</level> {message}',  # noqa: E501
        colorize=True,
        level=log_level,
    )
    logger.info(f'set log level to {log_level}')

    # check that the rsync binary exists
    if not shutil.which(RSYNC_BINARY):
        logger.error('rsync command is required')
        sys.exit(1)

    logger.info(f'rsync binary is {shutil.which(RSYNC_BINARY)}')

    # check that config exists
    if Path(config).is_file():
        config_file = Path(config).resolve()
    else:
        logger.error(f'no config file {config} found')
        sys.exit(1)

    logger.info(f'using config {config_file}')

    queue = SkipRepeatsQueue()

    worker_rsync = Thread(target=process_queue, args=(queue,))
    worker_rsync.setDaemon(True)
    worker_rsync.start()

    my_observers = []

    configurations = yaml.safe_load(config_file.read_bytes())
    for repo_name, repo_configuration in configurations.items():

        configuration = RepoConfig(**repo_configuration, name=repo_name)

        logger.info(
            'syncing repository named {} located in {} to {}'.format(
                configuration.name,
                configuration.source,
                configuration.destinations,
            )
        )

        my_observer = Observer()

        my_observer.schedule(
            EventHandler(configuration, queue),
            configuration.source,
            recursive=True,
        )

        my_observers.append(my_observer)

    logger.info('observers all initialized')

    for o in my_observers:
        o.start()

    try:
        while True:
            sleep(1)

    except KeyboardInterrupt:
        for o in my_observers:
            o.stop()
            o.join()


if __name__ == '__main__':
    main()

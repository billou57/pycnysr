# pycnysr

A simple directory watcher and syncer

# usage

Based on a YAML config file (see the [example configuration file](config.dist.yaml)), this module synchronizes a local directory to one or more local or remote directories, using [rsync](https://rsync.samba.org) as the underlying backend.

It uses two levels of exclusion and inclusion in order to avoid useless expensive rsync calls. At a first level, files that don't need to be monitored
can be excluded at a cheap cost. At a second level, only files that need to be
really rsynced can be configured and fine tuned.

It should be able to run on Windows, Linux and macOS and generate optional notifications.

# in practice

```yaml
my-repository:
  destinations: [
    "my-host:~/my-repository/"
  ]
  event_handler:
    excludes: [
      ".*tmp.*"
    ]
    includes: [
      ".*/api/.*",
      ".*/conf/.*",
    ]
  notify: true
  rsync:
    filters: [
      "- ***/*.pyc",
      "- ***/__pycache__/",
      "+ api/***",
      "+ conf/***",
      "- *"
    ]
    options: [
      '--archive',
      '--delete',
      '--rsh=ssh'
    ]
  source: ~/Sites/my-repository/
```

Given this `config.yaml` file, changes in the source directory `~/Sites/my-repository/` will be propagated to `my-host:~/my-repository/` via SSH with options eventually passed in the `rsync.options` list.

First, only files not excluded in the `event_handler.excludes` (by default: [])
and included by the `event_handler.includes` (by default: ['.*']) will be
passed to the rsync process.

Then, rsync is called with the [filter rules](https://download.samba.org/pub/rsync/rsync.1) built from the `rsync.filters` list.

Tet's run the watcher:

```console
❯ pycnysr --config config.yaml
2022-10-13 21:03:17 INFO set log level to INFO
2022-10-13 21:03:17 INFO rsync binary is /opt/homebrew/bin/rsync
2022-10-13 21:03:17 INFO using config /Users/laurent/Sites/pycnysr/config.yaml
2022-10-13 21:03:17 INFO syncing repository named my-repository located in /Users/laurent/Sites/pycnysr to ['/Users/laurent/Downloads/dest/']
2022-10-13 21:03:17 INFO observers all initialized
````

On another console, create a file:

```console
touch api/new-file.txt
```
See the file synchronized:

```console
2022-10-13 21:03:23 INFO synchronizing /Users/laurent/Sites/pycnysr/new-file.txt
```

# warning

Use with care. early development.

# license

This project is licensed under the terms of the MIT license.

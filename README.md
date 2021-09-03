# datasette-live-permissions

[![PyPI](https://img.shields.io/pypi/v/datasette-live-permissions.svg)](https://pypi.org/project/datasette-live-permissions/)
[![Changelog](https://img.shields.io/github/v/release/next-LI/datasette-live-permissions?include_prereleases&label=changelog)](https://github.com/next-LI/datasette-live-permissions/releases)
[![Tests](https://github.com/next-LI/datasette-live-permissions/workflows/Test/badge.svg)](https://github.com/next-LI/datasette-live-permissions/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/next-LI/datasette-live-permissions/blob/main/LICENSE)

A Datasette plugin that allows you to dynamically set permissions for users, groups, data and plugins using a new DB: `live_permissions.db`. In addition to checking and responding to permission requests, it also listens for new users and permissions and automatically adds them to the DB, easing management. This plugin integrates with the rest of the [datasette-live plugins][ds-live-topic].

## Installation

Install this plugin in the same environment as Datasette.

    $ datasette install datasette-live-permissions

## Usage

This plugin adds a database which will be populated with users, actions and resources that are requested from the various parts of Datasette. You can set configuration by granting access to users/groups to actions/resources via the `live_permissions` table.

Optionally, you can set the directory where the `live_permissions.db` file lives in your `metadata.yml`:

    datasette-live-permissions:
      db_path: /path/to/databases

By default, the directory is assumed to be the current working directory that Datasette is running from (e.g., `./`).

If you set this directory to somewhere what Datasette isn't expecting to look for databases, then you won't be able to change any permissions via the UI!


## Setting Permissions

Permissions in the permission database here, map back to permission check using Datasette's internal `datasette.permission_allowed` function.

```
await datasette.permission_allowed(
    actor, "view-database", ("my-database","my-table")
)
```

Is equivalent to the following row in the `actions_resources` table:

```
# Table: actions_resources (ids are arbitrary here)
id, action, resource_primary, resource_secondary
1, "view-database", "my-database", "my-table"
```

Leaving `resource_primary` and `resource_secondary` blank in any of these fields grants access to any permission checks regardless if that field is set or not. So, for example, to grant a user `view-database` access to al DBs and tables, you'd grant a user this `actions_resources` entry:

```
id, action, resource_primary, resource_secondary
2, "view-database", null, null
```

Same goes for users. Setting a value of `null` with a lookup key, will grant access to any user with that key set on their actor object. Etc etc. Be careful how you use null in your permissions!

## Permission Admins

The ability to change permissions is determined by the `"live-permissions-edit"` permission. You can restrict permission to a specific DB with the `("live-permissions-edit", DB_NAME)` permission tuple.

## Development

To set up this plugin locally, first checkout the code. Then create a new virtual environment:

    cd datasette-live-permissions
    python3 -mvenv venv
    source venv/bin/activate

Or if you are using `pipenv`:

    pipenv shell

Now install the dependencies and tests:

    pip install -e '.[test]'

To run the tests:

    pytest


[ds-live-topic]: https://github.com/topics/datasette-live
    "Datasette Live - GitHub Topic"

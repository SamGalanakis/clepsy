#!/bin/bash

# $1 will hold the argument passed from the postStartCommand in devcontainer.json
workspace_folder_basename=$1




# Configure Git
git config --global --add safe.directory /workspaces/$workspace_folder_basename
git config --global user.email $GIT_EMAIL
git config --global user.name $GIT_NAME
git config --global credential.helper store
# Install pre-commit hooks
echo "Setup completed for workspace: $workspace_folder_basename"



uv sync
uvx prek install --install-hooks

# uv run tailwindcss -i ./src/clepsy/frontend/css/app.css -o ./static/app.css




# baml-cli generate
# goose up

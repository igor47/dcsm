#!/bin/bash

# Path to the file to check
file_path="/templates/test"

# The expected content
expected_content="expected string"

# Check if the file exists
if [ ! -f "$file_path" ]; then
  echo "Error: File not found at $file_path"
  exit 1
fi

# Read the content of the file
content=$(<"$file_path")

# Check if the content matches the expected string
if [ "$content" == "$expected_content" ]; then
  echo "Success: File contains exactly the expected content."
  exit 0
else
  echo "Failure: File contains $content instead of expected $expected_content"
  exit 1
fi

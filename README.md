# Python Stub Extractor

Extracts type stubs from existing Python sources.

**Warning:** This script is experimental and very incomplete.
Don't expect that it does anything useful at this point.

## Dependencies

`stub_extractor` requires Python 3.8 or newer.

## Usage

There are two basic ways to run `stub_extractor`:

1. If no files are specified, `stub_extractor` will extract a type stub
   from stdin and print it to stdout:

   ```
   cat example.py | python3 stub_extractor
   ```

2. Otherwise, `stub_extractor` writes a stub file for each Python file
   given on the command line. The file will have the same name, but the
   `*.py` suffix will be replaced with `*.pyi`. If the target file already
   exists, `stub_extractor` will not overwrite it, unless the `-w` option
   is given.

   If a directory is specified, stubs for all Python files in the directory
   or its subdirectories are written.

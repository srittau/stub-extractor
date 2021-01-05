# Python Stub Extractor

Extracts type stubs from existing Python sources.

**Warning:** This script is experimental and very incomplete.
Don't expect that it does anything useful at this point.

## Dependencies

`stub_extractor` requires Python 3.8 or newer.

## Usage

`stub_extractor` will extract a type stub from stdin and print it
to stdout:

```
cat example.py | python3 stub_extractor
```

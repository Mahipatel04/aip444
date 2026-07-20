# Lab 8: img-debug - Visual Debugger

A CLI tool that analyzes screenshots of errors using a vision-capable AI model and web search.

## Installation

```bash
pip install openai tavily-python Pillow
```

## Setup

Create a `.env` file with  API keys:
OPENROUTER_API_KEY=
TAVILY_API_KEY=

## Usage

```bash
python img_debug.py <path_to_screenshot>
```

## Example

```bash
python img_debug.py error.png
```
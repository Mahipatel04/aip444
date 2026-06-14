# This is a simple test script to verify our read_github_files tool works
# before we connect it to the LLM. We test a few different cases:
# 1. A normal file (package.json from vscode)
# 2. A file that doesn't exist (404 error)
# 3. Two files at once (multi-file fetch)

from tools import read_github_files

def test():
    print("=" * 50)
    print("TEST 1: Normal file fetch")
    print("=" * 50)
    result = read_github_files([
        {
            "owner": "microsoft",
            "repo": "vscode",
            "path": "package.json",
            "ref": "main"
        }
    ])
    print(result[:500])  # Print first 500 chars so it's not too long
    print("\n")

    print("=" * 50)
    print("TEST 2: File that doesn't exist")
    print("=" * 50)
    result = read_github_files([
        {
            "owner": "microsoft",
            "repo": "vscode",
            "path": "this-file-does-not-exist.txt",
            "ref": "main"
        }
    ])
    print(result)
    print("\n")

    print("=" * 50)
    print("TEST 3: Two files at once")
    print("=" * 50)
    result = read_github_files([
        {
            "owner": "microsoft",
            "repo": "vscode",
            "path": "README.md",
            "ref": "main"
        },
        {
            "owner": "facebook",
            "repo": "react",
            "path": "README.md",
            "ref": "main"
        }
    ])
    print(result[:800])
    print("\n")

if __name__ == "__main__":
    test()
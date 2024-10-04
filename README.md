# glob-tries

## Description

`glob-tries` provides two classes, `GlobTrie` and `PathTrie`, which use slightly modified [trie](https://en.wikipedia.org/wiki/Trie) datastructures to efficiently store and query collections of globs and paths. These can be used for efficient indexing and matching of file trees when you have multiple glob patterns that might match a file. It also provides consistent precedence rules.
## Installation

```
pip install glob-tries
```

```
poetry add glob-tries
```

## Usage

```python
import glob_tries
```

### `GlobTrie`

`GlobTrie` can be thought of a `dict` where objects can be put into the dict using shell-style wildcard paths.

This is helpful in certain scenarios when you must group file paths, or file-path-like strings, into a variety of sets based on a variety of glob patterns. For example, say you have the following rules:

- All files in `/foo/bar/baz` are of group `baz`
- All `.yaml`, `.yml`, or `.json` files in `foo/*/baz` are in group `config`
- All other files in `foo` are in group `foo`
- All `.txt` files not otherwise covered by another rule should be in group `text`

You can express this with:

```python
from glob_tries import GlobTrie

trie = GlobTrie()

trie.augment("foo/bar/baz/**", "baz")
trie.augment("foo/*/baz/**/*.json", "config")
trie.augment("foo/*/baz/**/*.yaml", "config")
trie.augment("foo/*/baz/**/*.yml", "config")
trie.augment("foo/**", "foo")
trie.augment("**/*.txt", "text")
```

A call to `trie.get` with a path that matches these rules will return the correct group. Precedence is based on how "precise" a matching expression is; the matching expression will proceed left to right, trying more specific checks (single letters) before less specific checks (`**`). The order of evaluation is:

1. Single letters, as well as `[abc]`-type groups
2. `[!abc]`-type negative groups
3. `?` single-character wildcards
4. `*` single-folder wildcards
5. `**` recursive wildcards

`GlobTrie` supports `*`, `**`, `?`, `[abc]`, and `[!abc]`-style shell globbing.

```python
from glob_tries import GlobTrie

trie = GlobTrie()

trie.augment("foo", 1)
trie.augment("foo/*/bar", 2)
trie.augment("ba[rz]", 3)
trie.augment("ba[!m]", 4)
trie.augment("qu?z", 5)
trie.augment("spam/**/obj", 6)

trie.get("foo") # 1
trie.get("foobar") # None

trie.get("foo/baz/bar") # 2
trie.get("foo/egg/bar") # 2
trie.get("foo/egg/spam/bar") # None

trie.get("bar") # 3
trie.get("baz") # 3
trie.get("bam") # None
trie.get("bax") # 4

trie.get("quzz") # 5
trie.get("quaz") # 5
trie.get("quoz") # 5

trie.get("spam/obj") # 6
trie.get("spam/eggs/obj") # 6
trie.get("spam/ham/eggs/obj") # 6
trie.get("spam/ham/eggs/notobj") # None
```

### `PathTrie`

`PathTrie` is the inverse of `GlobTrie`. It stores a list of files in a directory, or strings that are arranged like files in a directory, and lets you efficiently list all files that match an arbitrary glob pattern. (The actual memory representation of the files is somewhat inefficient due to unavoidable Python overhead. Since each "node" in the trie is a Python object, there is a significant amount of overhead, meaning in many cases storing the trie representation of a list of many paths can be less efficient than just storing the list. It's computationally much more efficient to query, though.) `PathTrie` supports the same set of characters and operators as `GlobTrie`.

```python
from glob_tries import PathTrie

trie = PathTrie()

trie.augment("foo.py")
trie.augment("bar.py")
trie.augment("baz.py")
trie.augment("folder1/foo.py")
trie.augment("folder1/foo.yaml")
trie.augment("folder1/subfolder/foo.yaml")
trie.augment("folder2/foo.yaml")

trie.get_all_matches("foo.py")
# ["foo.py"]
trie.get_all_matches("ba[rz].py")
# ["bar.py", "baz.py"]
trie.get_all_matches("folder1/*")
# ["folder1/foo.py", "folder1/foo.yaml"]
trie.get_all_matches("folder1/**")
# ["folder1/foo.py", "folder1/foo.yaml", "folder1/subfolder/foo.yaml"]
trie.get_all_matches("folder1/**/*.yaml")
# ["folder1/foo.yaml", "folder1/subfolder/foo.yaml"]
trie.get_all_matches("**/*.yaml")
# ["folder1/foo.yaml", "folder2/foo.yaml", "folder1/subfolder/foo.yaml"]
```

## Contributing

We welcome contributions from the open-source community. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

The project currently has exhaustive test coverage. New additions should include similarly exhaustive coverage. Bugfixes should include a test that catches the bug condition. Unit tests can be run with `pytest`:

```
pytest
```

There are multiple pre-commit hooks that enforce typechecking, code style guidelines, and linter guidelines. Install them before development:

```
poetry run pre-commit install
```

## License

This library is licensed under the [BSD 3-Clause license](LICENSE).

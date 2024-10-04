# Copyright (c) 2024 Arcesium LLC. Licensed under the BSD 3-Clause license.
import re
from typing import Optional

import pytest

from glob_tries import GlobTrie, PathTrie

GLOBS = [
    ("foo.py", "foo"),
    ("fo[br].py", "fo-br"),
    ("fo[!obr].py", "fo-notobr"),
    ("*bar.py", "ends-with-bar"),
    ("spa?.py", "spam-or-spar"),
    ("**/*.y*ml", "yml-or-yaml"),
    ("**/baz.py", "baz-file"),
    ("**/namespace-*.yaml", "namespace-file"),
    ("**/bar/**/foo.py", "foo-in-bar"),
    ("bar/**", "bar-contents"),
    ("bar/*", "bar-single-level"),
    ("baz**/foo.py", "foo-path-starting-baz"),
    ("spam/**/foo.py", "spam-intermediate-foo"),
    ("egg*", "egg"),
    ("egg*/foo.py", "egg-foo"),
]


@pytest.fixture(scope="module")
def glob_trie() -> GlobTrie[str]:
    trie: GlobTrie[str] = GlobTrie()

    for glob, leaf in GLOBS:
        trie.augment(glob, leaf)
    return trie


@pytest.mark.parametrize(
    "expected,input",
    [
        ("foo", "foo.py"),
        (None, "*foo.py"),
        (None, "nothing.py"),
        ("fo-br", "fob.py"),
        ("fo-br", "for.py"),
        ("fo-notobr", "fol.py"),
        ("fo-notobr", "fop.py"),
        (None, "fo.py"),
        ("ends-with-bar", "bar.py"),
        ("ends-with-bar", "bababar.py"),
        ("ends-with-bar", "foobar.py"),
        ("spam-or-spar", "spam.py"),
        ("spam-or-spar", "spar.py"),
        (None, "spar.json"),
        ("yml-or-yaml", "foo.yaml"),
        ("yml-or-yaml", "foo.yml"),
        ("yml-or-yaml", ".yml"),
        ("yml-or-yaml", "foo/spam/eggs.yml"),
        ("yml-or-yaml", "foo/spam/eggs.yaml"),
        ("yml-or-yaml", "spam/eggs.yaml"),
        ("baz-file", "baz.py"),
        (None, "nothingbaz.py"),
        ("baz-file", "spam/baz.py"),
        ("baz-file", "spam/eggs/baz.py"),
        ("namespace-file", "app1/namespace-foo.yaml"),
        ("spam-intermediate-foo", "spam/foo/bar/baz/foo.py"),
        ("foo-in-bar", "cheese/bar/baz/foo.py"),
        ("foo-in-bar", "bar/baz/foo.py"),
        ("bar-single-level", "bar/foo.py"),
        ("foo-in-bar", "bar/eggs/foo.py"),
        ("bar-contents", "bar/eggs/something.py"),
        ("bar-contents", "bar/spam/something.yaml"),
        ("bar-contents", "bar/eggs/spam/something.yaml"),
        ("bar-contents", "bar/eggs/spam/something.yaml"),
        ("bar-single-level", "bar/something.yaml"),
        ("bar-single-level", "bar/something.py"),
        ("bar-single-level", "bar/"),
        ("foo-path-starting-baz", "bazfolder/foo.py"),
        ("foo-path-starting-baz", "bazfolder/spam/foo.py"),
        ("foo-path-starting-baz", "baz/spam/foo.py"),
        ("spam-intermediate-foo", "spam/spam/foo.py"),
        ("spam-intermediate-foo", "spam/foo.py"),
        ("spam-intermediate-foo", "spam/ham/eggs/foo.py"),
        (None, "spam/ham/eggsfoo.py"),
        (None, "spam/eggsfoo.py"),
        (None, "spam/ham/nothing/nothing.py"),
        ("egg", "egg"),
        ("egg", "egg.py"),
        ("egg", "egg.json"),
        ("egg-foo", "egg/foo.py"),
        ("egg-foo", "eggcrate/foo.py"),
        (None, "egg/crate/foo.py"),
        (None, "eggs/crate/foo.py"),
    ],
)
def test_glob_trie(expected: Optional[str], input: str, glob_trie):
    result = glob_trie.get(input)
    assert result == expected


@pytest.mark.parametrize("glob,name", GLOBS)
def test_glob_trie_duplicate(glob: str, name: str):
    trie: GlobTrie[str] = GlobTrie()

    # for every glob construct a string that gets matched by the glob
    matchable = re.sub(r"\[([^!]).*?\]", lambda m: m[1], glob)
    # this is ugly but works as long as we don't have any [!xyz_]
    matchable = re.sub(r"\[\!.*?\]", "_", matchable)
    matchable = matchable.replace("*", "")
    matchable = matchable.replace("?", "x")

    # returns False when it doesn't exist
    assert not trie.augment(glob, name)
    assert trie.get(matchable) == name

    # returns True the second time around
    assert trie.augment(glob, name + "1")
    assert trie.get(matchable) == name + "1"


PATHS = [
    "foo.py",
    "fob.py",
    "*foo.py",
    "endswithfoo.py",
    "baz/duck/bar/bam/quack/foo.py",
    "bar/foo.py",
    "barspam/foo.py",
    "bar/baz/foo.py",
    "bar/baz/foo.yaml",
    "bar/baz/foo.yml",
    "bar/baz/foo.json",
    "bar/baz/spamfoo.py",
    "bar/baz/wut/foo.py",
]


@pytest.fixture(scope="module")
def path_trie() -> PathTrie:
    trie: PathTrie = PathTrie()

    for path in PATHS:
        trie.augment(path)
    return trie


@pytest.mark.parametrize(
    "glob,expected",
    [
        ("foo.py", ("foo.py",)),
        ("fo?.py", ("fob.py", "foo.py")),
        ("*foo.py", ("endswithfoo.py", "*foo.py", "foo.py")),
        ("fo[o].py", ("foo.py",)),
        ("fo[!o].py", ("fob.py",)),
        ("[*]foo.py", ("*foo.py",)),
        (
            "**/foo.py",
            (
                "baz/duck/bar/bam/quack/foo.py",
                "bar/baz/foo.py",
                "bar/foo.py",
                "foo.py",
                "bar/baz/wut/foo.py",
                "barspam/foo.py",
            ),
        ),
        ("*/foo.py", ("bar/foo.py", "barspam/foo.py")),
        (
            "**/bar/**/foo.py",
            (
                "bar/foo.py",
                "bar/baz/wut/foo.py",
                "baz/duck/bar/bam/quack/foo.py",
                "bar/baz/foo.py",
            ),
        ),
        (
            "bar/**",
            (
                "bar/baz/foo.json",
                "bar/baz/foo.yml",
                "bar/baz/foo.py",
                "bar/baz/foo.yaml",
                "bar/baz/spamfoo.py",
                "bar/foo.py",
                "bar/baz/wut/foo.py",
            ),
        ),
        ("bar/*", ("bar/foo.py",)),
        (
            "bar/**/foo.py",
            ("bar/foo.py", "bar/baz/wut/foo.py", "bar/baz/foo.py"),
        ),
        (
            "bar/baz/*",
            (
                "bar/baz/foo.json",
                "bar/baz/foo.yml",
                "bar/baz/foo.py",
                "bar/baz/foo.yaml",
                "bar/baz/spamfoo.py",
            ),
        ),
        ("bar/baz/*.yaml", ("bar/baz/foo.yaml",)),
        ("bar/baz/foo.y*ml", ("bar/baz/foo.yml", "bar/baz/foo.yaml")),
        ("bar/baz/*.json", ("bar/baz/foo.json",)),
    ],
)
def test_path_trie(glob: str, expected: list[str], path_trie):
    result = set(path_trie.get_all_matches(glob))
    assert result == set(expected)


def test_path_trie_all(path_trie):
    # crosscheck against glob_match
    expected = set(PATHS)
    result = set(path_trie.get_all_matches("**"))
    assert result == expected

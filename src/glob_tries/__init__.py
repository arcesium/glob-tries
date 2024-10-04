# Copyright (c) 2024 Arcesium LLC. Licensed under the BSD 3-Clause license.
import sys
from typing import Generic, Optional, TypeVar, Union

# This file implements modified prefix trees, or "tries"
# (https://en.wikipedia.org/wiki/Trie), for efficiently matching file paths with
# corresponding glob patterns, and for efficiently finding a list of all files
# that match a glob pattern.

T = TypeVar("T")

# put these in vars
SLASH = ord("/")
STAR = ord("*")
QUESTION = ord("?")
L_SQUARE = ord("[")
R_SQUARE = ord("]")
BANG = ord("!")


class GlobTrie(Generic[T]):
    """
    Efficiently stores objects where their keys are shell-style glob patterns, and can
    be retrieved by providing a full path.
    """

    def __init__(self) -> None:
        self.leaf: Optional[T] = None
        # these come from plain characters, or from [xyz] or ? directives.
        self.match_children: dict[int, "GlobTrie[T]"] = {}
        # these come from [!xyz] directives, and also from ? directives (`a?` will put
        # "a" in match_children and notmatch_children
        # each key is a tuple of each char that we don't want to match
        self.notmatch_children: dict[int, "GlobTrie[T]"] = {}
        # result of a ?
        self.option_child: Union["GlobTrie[T]", None] = None
        # matches anything up to the next `/` char
        self.star_child: Union["GlobTrie[T]", None] = None
        # matches anything
        self.double_star_child: Union["GlobTrie[T]", None] = None

    def augment(self, glob: str, leaf: T) -> bool:
        """
        Augments the trie to match the provided `glob` to the provided `leaf`.
        Returns `False` if this pattern does not already exist in the trie; returns
        `True` if it does. If a value already exists in the trie for this glob, it will
        be overwritten.

        Params:
        - `glob`: The glob pattern
        - `leaf`: The object that this trie should return if there is a match.

        Returns `True` if there was already a leaf existing in the trie for the
        specified glob, and `False` otherwise.
        """

        # handle special case of **/: augment once with standard path, and once
        # with the first three removed
        glob_view = memoryview(bytes(glob, encoding="utf-8"))

        result = False
        if glob.startswith("**/") and len(glob) >= 4:
            result = self._augment(glob_view[3:], leaf)

        return self._augment(glob_view, leaf) or result

    def _augment(self, glob: memoryview, leaf: T) -> bool:
        # base case: if the glob is empty then we're done
        if len(glob) == 0:
            overwrite = False
            if self.leaf is not None:
                overwrite = True
            self.leaf = leaf
            return overwrite

        char = glob[0]
        rest = glob[1:]

        retval = False
        if char == L_SQUARE:
            try:
                positive_match = True
                if rest[0] == BANG:
                    # not matching
                    positive_match = False
                    rest = rest[1:]

                # consume chars until we hit the next "]"
                i = 0
                while True:
                    match_char = rest[i]
                    if match_char == R_SQUARE:
                        break
                    i += 1

                chars = rest[:i]
                rest = rest[i + 1 :]

                children = (
                    self.match_children
                    if positive_match
                    else self.notmatch_children
                )
                for char in chars:
                    child = children.get(char, None)

                    if child is None:
                        child = GlobTrie()
                        children[char] = child

                    retval = child._augment(rest, leaf) or retval
            except IndexError:
                raise ValueError("Unexpected end of string when we expected ]")
        elif char == STAR:  # star
            # check if it's a double star
            if len(rest) > 0 and rest[0] == STAR:
                if self.double_star_child is None:
                    self.double_star_child = GlobTrie()

                retval = (
                    self.double_star_child._augment(rest[1:], leaf) or retval
                )
            else:
                if self.star_child is None:
                    self.star_child = GlobTrie()

                retval = self.star_child._augment(rest, leaf) or retval
        elif char == QUESTION:  # question mark
            if self.option_child is None:
                self.option_child = GlobTrie()

            retval = self.option_child._augment(rest, leaf) or retval
        else:  # basic character
            child = self.match_children.get(char, None)
            if child is None:
                child = GlobTrie()
                self.match_children[char] = child

            retval = child._augment(rest, leaf) or retval

        return retval

    def get(self, path: str) -> Optional[T]:
        """
        If a glob pattern in the trie matches `path`, returns that pattern's value.
        Returns `None` if no match is found.
        """
        # use a memoryview to avoid copies
        return self._consume(memoryview(bytes(path, encoding="utf-8")), SLASH)

    # we need to provide the previous character so that we can handle special cases with
    # /*/ and /**/
    def _consume(self, input: memoryview, last: int) -> Optional[T]:
        # base case: if we're at the end of the input, return our leaf if it exists
        if len(input) == 0:
            retval = self.leaf
            # try star endings
            if retval is None and self.star_child is not None:
                retval = self.star_child._consume(input, last)

            if retval is None and self.double_star_child is not None:
                retval = self.double_star_child._consume(input, last)

            return retval

        char = input[0]
        rest = input[1:]

        # match the straightforward matches
        match_child = self.match_children.get(char, None)
        if match_child is not None:
            result = match_child._consume(rest, char)
            if result is not None:
                return result

        # match negative directives
        for not_char, child in self.notmatch_children.items():
            if not_char != char:
                result = child._consume(rest, char)
                if result is not None:
                    return result

        # match any single character
        if self.option_child is not None:
            result = self.option_child._consume(rest, char)
            if result is not None:
                return result

        # match star pattern
        if self.star_child is not None:
            # try consuming the input
            result = self.star_child._consume(input, last)
            if result is not None:
                return result

            # special case: if previous character was a "/" and star_child has a "/"
            if last == SLASH and SLASH in self.star_child.match_children.keys():
                no_subfolder_result = self.star_child.match_children[
                    SLASH
                ]._consume(input, last)

                if no_subfolder_result is not None:
                    return no_subfolder_result

            if char != SLASH:
                for i in range(len(input) + 1):
                    rest_result = self.star_child._consume(
                        input[i:], input[i - 1] if i > 0 else last
                    )
                    if rest_result is not None:
                        return rest_result
                    if i < len(input) and input[i] == SLASH:
                        break

        if self.double_star_child is not None:
            # need to special case coming in here with a / already

            # special case: if previous character was a "/" and star_child has a "/"
            if (
                last == SLASH
                and SLASH in self.double_star_child.match_children.keys()
            ):
                no_subfolder_result = self.double_star_child.match_children[
                    SLASH
                ]._consume(input, last)

                if no_subfolder_result is not None:
                    return no_subfolder_result

            for i in range(len(input) + 1):
                rest_result = self.double_star_child._consume(
                    input[i:], input[i - 1] if i > 0 else last
                )
                if rest_result is not None:
                    return rest_result

        # no matches
        return None

    def __str__(self):
        lines = [f"-> {self.leaf}"]
        lines.extend(self._strlines(0))

        return "\n".join(lines)

    def _strlines(self, indent: int) -> list[str]:
        spaces = " |" * indent
        lines = []

        for char, child in self.match_children.items():
            lines.append(f"{spaces}={chr(char)} -> {child.leaf}")
            lines.extend(child._strlines(indent + 1))

        for char, child in self.notmatch_children.items():
            lines.append(f"{spaces}!{chr(char)} -> {child.leaf}")
            lines.extend(child._strlines(indent + 1))

        if self.option_child:
            lines.append(f"{spaces}?  -> {self.option_child.leaf}")
            lines.extend(self.option_child._strlines(indent + 1))

        if self.star_child:
            lines.append(f"{spaces}*  -> {self.star_child.leaf}")
            lines.extend(self.star_child._strlines(indent + 1))

        if self.double_star_child:
            lines.append(f"{spaces}** -> {self.double_star_child.leaf}")
            lines.extend(self.double_star_child._strlines(indent + 1))

        return lines


class PathTrie:
    """
    Efficiently stores a list of files in a directory and its subdirectories, and
    enables fast retrieval of all files that match an arbitrary glob pattern.
    """

    def __init__(self) -> None:
        self.children: dict[int, "PathTrie"] = {}
        self.leaf = False

    def augment(self, path: str):
        """
        Store `path` in the trie.
        """
        self._augment(memoryview(bytes(path, encoding="utf-8")))

    def _augment(self, path: memoryview):
        if len(path) == 0:
            self.leaf = True
            return

        if path[0] not in self.children.keys():
            self.children[path[0]] = PathTrie()

        self.children[path[0]]._augment(path[1:])

    def get_all_matches(self, glob: str) -> list[str]:
        """
        Get a list of the paths of all files that have been added by `augment()` that
        match the provided glob.
        """

        results = []
        glob_view = memoryview(bytes(glob, encoding="utf-8"))
        if glob.startswith("**/") and len(glob) > 3:
            # special case of **/ at beginning of path. First, consume the glob without
            # the starting path to pick up matches in the root dir. Then, we'll
            # consume it as usual, which will require a "/" before matching the rest.
            # This lets "**/foo.txt" match "foo.txt" and "bar/foo.txt" but not
            # "xfoo.txt".
            results.extend(self._consume(glob_view[3:]))

        results.extend(self._consume(glob_view))

        return [bytes(result[::-1]).decode() for result in results]

    def _consume(self, glob: memoryview) -> list[list[int]]:
        if len(glob) == 0:
            return [[]] if self.leaf else []

        char = glob[0]
        rest = glob[1:]

        paths: list[list[int]] = []
        if char == STAR:
            # check for double asterisk
            double_asterisk = len(rest) > 0 and rest[0] == STAR

            for char, subtrie in self.children.items():
                if char == SLASH and not double_asterisk:
                    continue

                subpaths = subtrie._consume(glob)

                for subpath in subpaths:
                    # we first assemble all paths backwards to avoid unnecessary copying
                    subpath.append(char)

                paths.extend(subpaths)

            # now we chop the stars off the front and try searching again
            next_index = 1 if double_asterisk else 0
            paths.extend(self._consume(rest[next_index:]))
        elif char == L_SQUARE:
            try:
                positive_match = True
                if rest[0] == BANG:
                    # not matching
                    positive_match = False
                    rest = rest[1:]

                # consume chars until we hit the next "]"
                i = 0
                while True:
                    match_char = rest[i]
                    if match_char == R_SQUARE:
                        break
                    i += 1

                chars = rest[:i]
                rest = rest[i + 1 :]

                if positive_match:
                    for match_char in chars:
                        child = self.children.get(match_char, None)
                        if child is None:
                            continue

                        pos_subpaths = child._consume(rest)
                        for subpath in pos_subpaths:
                            # assemble backwards
                            subpath.append(match_char)
                        paths.extend(pos_subpaths)

                else:
                    for match_char, subtrie in self.children.items():
                        if match_char not in chars:
                            neg_subpaths: list[list[int]] = subtrie._consume(
                                rest
                            )

                            for subpath in neg_subpaths:
                                # assemble backwards
                                subpath.append(match_char)
                            paths.extend(neg_subpaths)

            except IndexError:
                raise ValueError("Unexpected end of string when we expected ]")
        elif char == QUESTION:
            for next_char, subtrie in self.children.items():
                subpaths = subtrie._consume(rest)

                for subpath in subpaths:
                    # we first assemble all paths backwards to avoid unnecessary copying
                    subpath.append(next_char)

                paths.extend(subpaths)
        else:  # basic character
            next_index = 0

            char_subpaths = []
            child = self.children.get(char, None)
            if child is None:
                return []

            if len(rest) >= 1 and char == SLASH and rest[0] == STAR:
                # try skipping the stars and slash entirely, and only parse the
                # remainder of the pattern
                if len(rest) >= 3 and rest[1] == STAR and rest[2] == SLASH:
                    # handle /**/
                    char_subpaths.extend(child._consume(rest[3:]))
                elif len(rest) >= 2 and rest[1] == SLASH:
                    # handle /*/
                    char_subpaths.extend(child._consume(rest[2:]))

            char_subpaths.extend(child._consume(rest[next_index:]))
            for subpath in char_subpaths:
                subpath.append(char)
            paths.extend(char_subpaths)

        return paths

    def __str__(self):
        return "\n".join(self._strlines(0))

    def _strlines(self, indent: int) -> list[str]:
        spaces = "| " * indent
        lines = []
        for char, subtrie in self.children.items():
            lines.append(f"{spaces}{chr(char)}")
            lines.extend(subtrie._strlines(indent + 1))

        return lines

    def __sizeof__(self):
        ret = sys.getsizeof(self.leaf)
        ret += sys.getsizeof(self.children)
        ret += sum([child.__sizeof__() for child in self.children.values()])

        return ret

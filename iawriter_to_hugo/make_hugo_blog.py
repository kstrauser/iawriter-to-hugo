#!/usr/bin/env python

"""Tool for converting a directory of iA Writer Markdown files to a Hugo blog."""

import logging
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from xdg_base_dirs import xdg_config_home

LOG = logging.getLogger(__name__)

LINK = re.compile(r"(\[\[(.*?)(?:\|(.*?))?\]\])")
IMAGES = re.compile(
    r'^(([a-z0-9_-]+\.(?:png|jpe?g))(?:\s+"?(.*?)"?)?)\s*?$',
    re.MULTILINE | re.IGNORECASE,
)

CONF_FILE = xdg_config_home() / "iawriter_to_hugo" / "config.toml"
CONF = tomllib.load(CONF_FILE.open("rb"))

WRITER_POST_DIR = Path(CONF["writer_post_dir"])
WRITER_IMAGE_DIR = Path(CONF["writer_image_dir"])
HUGO_POST_DIR = Path(CONF["hugo_post_dir"])
HUGO_IMAGE_DIR = Path(CONF["hugo_image_dir"])
EMPTY_BODY = CONF["empty_body_text"]


@dataclass
class Link:
    """Represent an internal link between Markdown documents."""

    text: str
    name: str
    alias: str

    @property
    def title(self) -> str:
        """Return the link's title as it should appear on the web page."""
        return self.alias if self.alias else self.name

    @property
    def slug(self) -> str:
        """Return the link's slug."""
        return slug(self.name)


@dataclass
class Image:
    """An image reference from a Markdown document."""

    text: str
    image: str
    caption: str


@dataclass
class Post:
    """A Markdown post, as stored in iA Writer."""

    post_file: Path
    raw_body: str

    @property
    def title(self) -> str:
        """Return the post's human-friendly title."""
        if self.raw_body.startswith("#"):
            return self.raw_body.splitlines()[0].lstrip("#").strip()
        return self.post_file.stem

    def as_hugo(self, refs: set[str]) -> str:
        """Return the Hugo-formatted version of the post's contents."""
        body = self.raw_body.strip()
        if not body:
            body = EMPTY_BODY

        for link in links_from(body):
            body = body.replace(link.text, hugo_link(link.title, link.slug))

        for image in images_from(body):
            copy_image(image.image)
            body = body.replace(image.text, f"![{image.caption}](/{image.image})")

        if not body.startswith("#"):
            body = markdown_title(self.title) + body

        return hugo_header(self.title) + body + reference_list(refs)


def markdown_title(title: str) -> str:
    """Return the Markdown-formatted post title."""
    return f"# {title}\n\n"


def images_from(body: str) -> list[Image]:
    """Return a list of images found in the post body."""
    return [Image(*_) for _ in IMAGES.findall(body)]


def links_from(body: str) -> list[Link]:
    """Return a list of internal links found in the post body."""
    return [Link(*_) for _ in LINK.findall(body)]


def copy_image(filename: str):
    """Copy the named image from iA Writer to Hugo, if it's not already there and current."""
    src_file = WRITER_IMAGE_DIR / filename
    dest_file = HUGO_IMAGE_DIR / filename

    if dest_file.is_file() and dest_file.stat().st_mtime >= src_file.stat().st_mtime:
        return

    dest_file.write_bytes(src_file.read_bytes())


def hugo_header(title: str) -> str:
    """Create a Hugo YAML front matter for the post."""
    return f'---\ntitle: "{title}"\n---\n'


def hugo_link(title: str, slug: str) -> str:
    """Create a Hugo-flavored Markdown link to the article."""
    return f'[{title}]({{{{< ref "/docs/{slug}" >}}}})'


def fake_post(title: str, refs: set[str]) -> str:
    """Make an empty blog post in the same format as a real one."""
    return hugo_header(title) + markdown_title(title) + EMPTY_BODY + reference_list(refs)


def reference_list(refs: set[str]) -> str:
    """Make a Markdown block of posts that refer to this one."""
    if not refs:
        return ""

    text = "\n\n---\n## References\n"
    for ref_title in sorted(refs):
        ref_slug = slug(ref_title)
        text += f"- {hugo_link(ref_title, ref_slug)}\n"
    return text


def slug(title: str) -> str:
    """Convert a post's title into a reasonable URL slug."""
    title = title.lower()
    for char in "'’.":
        title = title.replace(char, "")
    title = title.replace(" ", "_")
    while "__" in title:
        title = title.replace("__", "_")
    return title


def main() -> None:
    """Convert iA Writer Markdown files to Hugo blog posts."""
    log_level = {
        0: logging.WARNING,
        1: logging.INFO,
        2: logging.DEBUG,
    }.get(sys.argv[1:].count("-v"), logging.DEBUG)
    logging.basicConfig(level=log_level)

    refs: dict[str, set[str]] = {}
    posts: dict[str, Post] = {}

    # First, load the Markdown files and build a map of references between them.
    for post_file in WRITER_POST_DIR.glob("*.md"):
        post = Post(post_file, post_file.read_text())
        posts[slug(post.title)] = post
        for link in links_from(post.raw_body):
            try:
                ref = refs[link.name]
            except KeyError:
                ref = refs[link.name] = set()
            ref.add(post.title)

    # Next, write out existing files in Hugo format.
    for post in posts.values():
        post_dir = HUGO_POST_DIR / slug(post.title)
        post_dir.mkdir(parents=True, exist_ok=True)
        post_file = post_dir / "index.md"
        post_refs = refs.get(post.title, set())
        LOG.info("Writing %r to %s with refs %r", post.title, post_file, post_refs)
        post_file.write_text(post.as_hugo(post_refs))

    # Finally, make placeholder blog posts for pages that were referred
    # to but that don't already exist.
    for post_title, post_refs in refs.items():
        post_slug = slug(post_title)
        if post_slug in posts:
            continue
        post_dir = HUGO_POST_DIR / post_slug
        post_dir.mkdir(parents=True, exist_ok=True)
        post_file = post_dir / "index.md"
        LOG.info("Writing fake post %r to %s because of %r", post_title, post_file, post_refs)
        post_file.write_text(fake_post(post_title, post_refs))


if __name__ == "__main__":
    main()

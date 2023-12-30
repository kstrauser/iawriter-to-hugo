# Convert an iA Writer directory to a Hugo blog's contents

## Installation

Run `poetry install`.

Copy `config-example.toml` to `~/.config/iawriter_to_hugo/config.toml` and edit it appropriately.

## Usage

Run `poetry run make-hugo-blog` to convert the Markdown files to Hugo.

Note that `make-hugo-blog` overwrites all files it knows about (so don't hand-edit files after they've been generated), and ignores files it doesn't know about (so you're responsible for deleting old files if you want them to go away).

If you're using this to maintain all of the blog's content, consider running `rm -rf ${hugo_post_dir}` each time and letting `make-hugo-blog` re-recreate all the files from scratch.

# Xiaohongshu Posts Directory

This directory is where you prepare your content for automatic posting to Xiaohongshu.

## How to Use

1.  **Create a sub-directory for each post.** For example: `my_first_post/`.
2.  The name of this sub-directory will be used as the post's title.

### Inside Each Post Directory:

- **Images**: Place all image files (e.g., `.jpg`, `.png`) you want to include in the post. The script will currently only upload the **first** image it finds.
- **Text Content**: Create a single text file (e.g., `content.txt` or `post.md`). The entire content of this file will be used as the post's description, including any hashtags you write.

**Example Structure:**

```
tmp/xiaohongshu_posts/
└── my_awesome_post/
    ├── image1.jpg
    ├── image2.png
    └── content.txt
```

In the example above:

- The post title will be `my_awesome_post`.
- `image1.jpg` will be uploaded.
- The full content of `content.txt` will be the description.

**Note**: The contents of this directory (your posts) are ignored by Git. Only this `README.md` and a `.gitkeep` file are tracked.
